"""Qdrant KB payload migration: legacy role_id -> role_ids[] (M2)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class QdrantPointRecord:
    point_id: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class QdrantPayloadUpdate:
    point_id: str
    role_ids: list[str]
    previous_role_ids: list[str] | None


@dataclass(frozen=True)
class QdrantMigrationPlan:
    total_points: int
    updates: tuple[QdrantPayloadUpdate, ...]


@dataclass(frozen=True)
class QdrantMigrationResult:
    applied: bool
    message: str
    plan: QdrantMigrationPlan | None = None
    points_updated: int = 0


def extract_payload_role_ids(payload: dict[str, Any]) -> set[str]:
    roles: set[str] = set()
    raw_ids = payload.get("role_ids")
    if isinstance(raw_ids, list):
        for item in raw_ids:
            role_id = str(item).strip()
            if role_id:
                roles.add(role_id)
    legacy = str(payload.get("role_id") or "").strip()
    if legacy:
        roles.add(legacy)
    return roles


def build_doc_role_union(points: list[QdrantPointRecord]) -> dict[str, list[str]]:
    grouped: dict[str, set[str]] = {}
    for point in points:
        doc_id = str(point.payload.get("doc_id") or "").strip()
        if not doc_id:
            continue
        grouped.setdefault(doc_id, set()).update(extract_payload_role_ids(point.payload))
    return {doc_id: sorted(role_ids) for doc_id, role_ids in grouped.items()}


def plan_qdrant_payload_migration(points: list[QdrantPointRecord]) -> QdrantMigrationPlan:
    doc_roles = build_doc_role_union(points)
    updates: list[QdrantPayloadUpdate] = []

    for point in points:
        doc_id = str(point.payload.get("doc_id") or "").strip()
        if not doc_id:
            continue
        target_role_ids = doc_roles.get(doc_id, [])
        if not target_role_ids:
            continue

        current = point.payload.get("role_ids")
        previous = list(current) if isinstance(current, list) else None
        if isinstance(current, list) and sorted(str(x) for x in current) == target_role_ids:
            continue

        updates.append(
            QdrantPayloadUpdate(
                point_id=point.point_id,
                role_ids=target_role_ids,
                previous_role_ids=previous,
            )
        )

    return QdrantMigrationPlan(total_points=len(points), updates=tuple(updates))


def format_qdrant_migration_plan(plan: QdrantMigrationPlan) -> str:
    lines = [
        f"total points: {plan.total_points}",
        f"points to update: {len(plan.updates)}",
        "",
    ]
    for update in plan.updates[:20]:
        lines.append(
            f"  {update.point_id}: role_ids {update.previous_role_ids} -> {update.role_ids}"
        )
    if len(plan.updates) > 20:
        lines.append(f"  ... and {len(plan.updates) - 20} more")
    return "\n".join(lines)


class QdrantScrollClient(Protocol):
    def scroll(
        self,
        collection_name: str,
        *,
        limit: int,
        offset: Any | None = None,
        with_payload: bool = True,
    ) -> tuple[list[Any], Any | None]: ...

    def set_payload(
        self,
        collection_name: str,
        payload: dict[str, Any],
        points: list[str],
        *,
        wait: bool = True,
    ) -> None: ...


def scroll_all_points(client: QdrantScrollClient, collection: str) -> list[QdrantPointRecord]:
    records: list[QdrantPointRecord] = []
    offset: Any | None = None
    while True:
        batch, next_offset = client.scroll(
            collection,
            limit=256,
            offset=offset,
            with_payload=True,
        )
        for point in batch:
            payload = point.payload if isinstance(point.payload, dict) else {}
            records.append(QdrantPointRecord(point_id=str(point.id), payload=payload))
        if next_offset is None:
            break
        offset = next_offset
    return records


def apply_qdrant_payload_migration(
    client: QdrantScrollClient,
    collection: str,
    *,
    dry_run: bool = True,
) -> QdrantMigrationResult:
    points = scroll_all_points(client, collection)
    plan = plan_qdrant_payload_migration(points)

    if dry_run:
        return QdrantMigrationResult(
            applied=False,
            message="dry-run: no Qdrant payload changes written",
            plan=plan,
        )

    updated = 0
    for update in plan.updates:
        client.set_payload(
            collection,
            {"role_ids": update.role_ids},
            [update.point_id],
            wait=True,
        )
        updated += 1

    return QdrantMigrationResult(
        applied=True,
        message=f"updated role_ids on {updated} Qdrant points in {collection}",
        plan=plan,
        points_updated=updated,
    )
