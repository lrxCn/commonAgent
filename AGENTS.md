# CommonAgent Agent Instructions

This file is the cross-tool instruction source for Codex, Cursor, Antigravity, and any other AI agent working in this repository. Tool-specific files may exist only as adapters that point back here.

## Read Order

Before changing files, read:

1. [README.md](README.md) for architecture, setup, API, memory, RAG, and `client_actions` contracts.
2. [docs/progress.md](docs/progress.md) for current task status and dependencies.
3. The relevant [docs/prompts/](docs/prompts/) task card when implementing a prompt task.

If you work inside `agent/`, also read [agent/AGENTS.md](agent/AGENTS.md) for graph invocation details.

## Source Of Truth

- `README.md` is the project architecture and operating contract.
- `AGENTS.md` is the cross-tool behavior contract for AI agents.
- `docs/progress.md` is the progress ledger.
- `docs/prompts/*.md` are task-level implementation scopes.
- `.cursor/skills/*/SKILL.md` are Cursor adapters only; do not duplicate core rules there.

## Working Rules

- Keep changes scoped to the requested task.
- Do not overwrite user changes. If existing edits affect the task, work with them.
- Do not commit, push, or create PRs unless explicitly asked.
- Do not commit `.env` files or real secrets.
- When changing `.env` contracts, update the matching `.env.example` with masked example values.
- Prefer existing project patterns over new abstractions.
- Use `rg` / `rg --files` for repository search.
- Run the relevant tests from the task card or the smallest meaningful test set for the change.
- If tests cannot run because local services are missing, run mock/unit coverage and report what was skipped.

## Prompt Task Workflow

When executing one task under `docs/prompts/`:

1. Identify exactly one task card.
2. Read `README.md`, `docs/progress.md`, then the task card.
3. Check dependencies in `docs/progress.md`; stop if required dependencies are not complete.
4. Implement only the task scope. Do not take adjacent tasks.
5. Run the task card's test plan.
6. Only after tests pass, update `docs/progress.md` if the task status changes.

## Contract Change Workflow

If a task card or user request changes architecture, API fields, state/context rules, memory semantics, RAG flow, `client_actions`, directory layout, or environment contracts:

1. Update `README.md` in the same change.
2. Update affected task cards only when their scope/API would otherwise become misleading.
3. Update `docs/progress.md` changelog for documentation-only contract changes.

## Core Project Constraints

- Agent is internal-only; browsers must go through Back.
- `thread_id` is the checkpoint key.
- `user_id`, `role_id`, and `tools[]` are per-turn request context and must not be trusted from checkpoint state.
- External tools are emitted as `client_actions`; Agent does not execute them, wait for results, or resume.
- Back owns authentication, role calculation, and external tool whitelist filtering.
- Front owns `thread_id` storage and client action execution/approval.
- mem0 is local OSS `Memory` + local/internal Qdrant only. Do not use mem0 cloud, `MemoryClient`, `MEM0_API_KEY`, or `api.mem0.ai`.
- `MEM0_MOCK` and `QDRANT_MOCK` runtime defaults are `false`; tests should not assume mock defaults unless explicitly configured.

## Frontend Notes

If working on `front/`, keep the first screen as the usable app, not a marketing page. Preserve the current Front -> Back -> Agent boundary and do not make the browser call Agent directly.
