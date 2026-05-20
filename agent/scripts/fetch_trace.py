#!/usr/bin/env python3
"""Fetch a LangSmith trace by root run / trace ID (loads agent/.env automatically)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from langsmith import Client

_AGENT_DIR = Path(__file__).resolve().parent.parent
_DEFAULT_ENV = _AGENT_DIR / ".env"


def load_agent_env(env_path: Path | None = None) -> Path | None:
    """Load KEY=VALUE lines from agent/.env into os.environ (no override)."""
    path = env_path or _DEFAULT_ENV
    if not path.is_file():
        return None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        os.environ.setdefault(key, value)
    # LangSmith SDK accepts LANGCHAIN_API_KEY; mirror from LANGSMITH_API_KEY
    if not os.environ.get("LANGCHAIN_API_KEY") and os.environ.get("LANGSMITH_API_KEY"):
        os.environ.setdefault("LANGCHAIN_API_KEY", os.environ["LANGSMITH_API_KEY"])
    return path


def _project_name() -> str:
    return (
        os.environ.get("LANGCHAIN_PROJECT")
        or os.environ.get("LANGSMITH_PROJECT")
        or "common-agent"
    )


def _to_dict(run: Any) -> dict[str, Any]:
    if hasattr(run, "model_dump"):
        return run.model_dump(mode="json")
    return run.dict()


def _latency_ms(run: Any) -> int | None:
    if not run.end_time or not run.start_time:
        return None
    return int((run.end_time - run.start_time).total_seconds() * 1000)


def _short(value: Any, limit: int = 160) -> str:
    if value is None:
        return ""
    text = str(value).replace("\n", " ").replace("|", "\\|")
    if len(text) <= limit:
        return text
    return f"{text[:limit]}…({len(text)} chars)"


def load_trace(client: Client, run_id: str, project: str) -> tuple[Any, list[Any]]:
    root = client.read_run(run_id)
    trace_id = str(root.trace_id or root.id)
    runs = list(
        client.list_runs(
            project_name=project,
            trace_id=trace_id,
        )
    )
    return root, runs


def summary_payload(root: Any, runs: list[Any]) -> dict[str, Any]:
    ordered = sorted(runs, key=lambda r: r.start_time or datetime.min)
    rows: list[dict[str, Any]] = []
    for run in ordered:
        extra = run.extra or {}
        meta = extra.get("metadata", {}) if isinstance(extra, dict) else {}
        rows.append(
            {
                "id": str(run.id),
                "name": run.name,
                "run_type": run.run_type,
                "status": run.status,
                "parent_run_id": str(run.parent_run_id) if run.parent_run_id else None,
                "tags": list(run.tags or []),
                "metadata": meta if isinstance(meta, dict) else {},
                "error": _short(run.error, 300) or None,
                "latency_ms": _latency_ms(run),
                "total_tokens": run.total_tokens,
            }
        )
    return {
        "project": _project_name(),
        "root_run_id": str(root.id),
        "root_name": root.name,
        "trace_id": str(root.trace_id or root.id),
        "status": root.status,
        "start_time": str(root.start_time),
        "end_time": str(root.end_time),
        "run_count": len(runs),
        "runs": rows,
    }


def full_payload(root: Any, runs: list[Any]) -> dict[str, Any]:
    return {
        "project": _project_name(),
        "root": _to_dict(root),
        "runs": [_to_dict(r) for r in runs],
    }


def render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# LangSmith Trace 摘要",
        "",
        f"- **project**: `{summary['project']}`",
        f"- **root_run_id**: `{summary['root_run_id']}`",
        f"- **root_name**: {summary['root_name']}",
        f"- **trace_id**: `{summary['trace_id']}`",
        f"- **status**: {summary['status']}",
        f"- **start**: {summary['start_time']}",
        f"- **end**: {summary['end_time']}",
        f"- **span 数**: {summary['run_count']}",
        "",
        "## 流水线",
        "",
        "| # | name | type | status | ms | tokens | tags | error |",
        "|---|------|------|--------|-----|--------|------|-------|",
    ]
    for i, row in enumerate(summary["runs"], 1):
        tags = ", ".join(row["tags"]) if row["tags"] else ""
        err = row["error"] or ""
        ms = row["latency_ms"] if row["latency_ms"] is not None else ""
        tok = row["total_tokens"] if row["total_tokens"] is not None else ""
        lines.append(
            f"| {i} | {row['name']} | {row['run_type']} | {row['status']} "
            f"| {ms} | {tok} | {_short(tags, 40)} | {_short(err, 60)} |"
        )
    meta_runs = [r for r in summary["runs"] if r.get("metadata")]
    if meta_runs:
        lines.extend(["", "## Metadata（有值的 span）", ""])
        for row in meta_runs:
            lines.append(f"### `{row['name']}` (`{row['id'][:8]}…`)")
            lines.append("```json")
            lines.append(json.dumps(row["metadata"], ensure_ascii=False, indent=2))
            lines.append("```")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def list_recent_roots(client: Client, project: str, limit: int, minutes: int | None) -> list[Any]:
    kwargs: dict[str, Any] = {
        "project_name": project,
        "is_root": True,
        "limit": limit,
    }
    if minutes is not None:
        kwargs["start_time"] = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    return list(client.list_runs(**kwargs))


def latest_root_run(client: Client, project: str, minutes: int | None) -> Any | None:
    roots = list_recent_roots(client, project, limit=1, minutes=minutes)
    return roots[0] if roots else None


def trace_log_filename(root: Any) -> str:
    """Filesystem-safe name from run start time + short id."""
    start = root.start_time
    if start is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    else:
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        stamp = start.astimezone(timezone.utc).strftime("%Y%m%d_%H%M%S")
    short_id = str(root.id).replace("-", "")[:8]
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in (root.name or "trace"))
    return f"{stamp}_{safe_name}_{short_id}.json"


def resolve_logs_dir(path: Path | None) -> Path:
    logs = path if path is not None else _AGENT_DIR / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    return logs


def cmd_list(client: Client, project: str, limit: int, minutes: int | None) -> int:
    roots = list_recent_roots(client, project, limit, minutes)
    if not roots:
        print("No root runs found.", file=sys.stderr)
        return 1
    print(f"project={project}  roots={len(roots)}\n")
    for run in roots:
        ms = _latency_ms(run)
        print(
            f"{run.id}  {run.status:8}  {ms or 0:6}ms  "
            f"{run.start_time}  {run.name}"
        )
    return 0


def cmd_fetch(
    client: Client,
    project: str,
    run_id: str,
    *,
    full: bool,
    markdown: bool,
    output: Path | None,
) -> int:
    root, runs = load_trace(client, run_id, project)
    summary = summary_payload(root, runs)

    if markdown:
        text = render_markdown(summary)
        if output:
            output.write_text(text, encoding="utf-8")
            print(f"Wrote markdown to {output}", file=sys.stderr)
        else:
            print(text)
        return 0

    payload: dict[str, Any] = full_payload(root, runs) if full else summary
    text = json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    if output:
        output.write_text(text, encoding="utf-8")
        print(
            f"Wrote trace {summary['trace_id']} ({len(runs)} spans) to {output}",
            file=sys.stderr,
        )
    else:
        print(text)
    return 0


def cmd_latest(
    client: Client,
    project: str,
    *,
    full: bool,
    logs_dir: Path,
    minutes: int | None,
) -> int:
    root = latest_root_run(client, project, minutes)
    if root is None:
        print("No root runs found.", file=sys.stderr)
        return 1

    run_id = str(root.id)
    out_path = resolve_logs_dir(logs_dir) / trace_log_filename(root)
    print(f"Latest root run: {run_id} ({root.name}, {root.start_time})", file=sys.stderr)
    return cmd_fetch(
        client,
        project,
        run_id,
        full=full,
        markdown=False,
        output=out_path,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch LangSmith trace from commonAgent (reads agent/.env).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s 019e4290-4d11-7fe0-b078-a4b27a0fbade
  %(prog)s <run-id> --markdown -o ../temp.md
  %(prog)s <run-id> --full -o /tmp/trace.json
  %(prog)s --list --limit 5
  %(prog)s --latest
  %(prog)s --latest --full
        """,
    )
    parser.add_argument(
        "run_id",
        nargs="?",
        help="Root run / trace UUID from LangSmith Studio (top agent layer)",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=_DEFAULT_ENV,
        help=f"Env file path (default: {_DEFAULT_ENV})",
    )
    parser.add_argument(
        "--project",
        help="Override LANGCHAIN_PROJECT / LANGSMITH_PROJECT",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Export full run payloads (default: summary JSON)",
    )
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="Write human-readable markdown (use with -o for temp.md)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output file path (default: stdout)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List recent root runs in the project",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="With --list: max root runs (default 10)",
    )
    parser.add_argument(
        "--last-minutes",
        type=int,
        metavar="N",
        help="With --list / --latest: only runs from the last N minutes",
    )
    parser.add_argument(
        "--latest",
        action="store_true",
        help="Fetch the newest root run into ./logs/ as timestamped JSON",
    )
    parser.add_argument(
        "--logs-dir",
        type=Path,
        default=_AGENT_DIR / "logs",
        help="Output directory for --latest (default: agent/logs)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    loaded = load_agent_env(args.env_file)
    if loaded:
        print(f"Loaded env from {loaded}", file=sys.stderr)
    elif not os.environ.get("LANGSMITH_API_KEY") and not os.environ.get("LANGCHAIN_API_KEY"):
        print(
            "Warning: no LANGSMITH_API_KEY in env; set agent/.env or export key.",
            file=sys.stderr,
        )

    if args.project:
        os.environ["LANGCHAIN_PROJECT"] = args.project

    project = _project_name()
    client = Client()

    if args.list:
        return cmd_list(client, project, args.limit, args.last_minutes)

    if args.latest:
        if args.run_id:
            print("Warning: run_id ignored when --latest is set.", file=sys.stderr)
        if args.markdown:
            print("Warning: --markdown ignored for --latest (JSON only).", file=sys.stderr)
        if args.output:
            print("Warning: -o ignored for --latest (uses --logs-dir).", file=sys.stderr)
        return cmd_latest(
            client,
            project,
            full=args.full,
            logs_dir=args.logs_dir,
            minutes=args.last_minutes,
        )

    if not args.run_id:
        build_parser().print_help()
        return 2

    return cmd_fetch(
        client,
        project,
        args.run_id,
        full=args.full,
        markdown=args.markdown,
        output=args.output,
    )


if __name__ == "__main__":
    raise SystemExit(main())
