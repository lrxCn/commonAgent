"""Tests for Qdrant KB payload role_ids[] migration (task 97)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from rag.kb_payload_migration import (
    QdrantPointRecord,
    apply_qdrant_payload_migration,
    plan_qdrant_payload_migration,
)


class FakeScrollClient:
    def __init__(self, points: list[QdrantPointRecord]) -> None:
        self.points = points
        self.payload_updates: list[tuple[str, dict[str, Any], list[str]]] = []

    def scroll(
        self,
        collection_name: str,
        *,
        limit: int,
        offset: Any | None = None,
        with_payload: bool = True,
    ) -> tuple[list[MagicMock], Any | None]:
        start = int(offset or 0)
        end = min(start + limit, len(self.points))
        batch = []
        for record in self.points[start:end]:
            point = MagicMock()
            point.id = record.point_id
            point.payload = record.payload
            batch.append(point)
        next_offset = end if end < len(self.points) else None
        return batch, next_offset

    def set_payload(
        self,
        collection_name: str,
        payload: dict[str, Any],
        points: list[str],
        *,
        wait: bool = True,
    ) -> None:
        self.payload_updates.append((collection_name, payload, points))


def test_plan_merges_role_ids_per_doc_id() -> None:
    points = [
        QdrantPointRecord(
            point_id="p1",
            payload={
                "doc_id": "doc-a",
                "role_id": "role-sales",
                "chunk_id": "doc-a:1:0000",
                "text": "chunk 1",
            },
        ),
        QdrantPointRecord(
            point_id="p2",
            payload={
                "doc_id": "doc-a",
                "role_id": "role-support",
                "chunk_id": "doc-a:1:0001",
                "text": "chunk 2",
            },
        ),
    ]

    plan = plan_qdrant_payload_migration(points)

    assert len(plan.updates) == 2
    for update in plan.updates:
        assert update.role_ids == ["role-sales", "role-support"]


def test_plan_skips_already_migrated_points() -> None:
    points = [
        QdrantPointRecord(
            point_id="p1",
            payload={
                "doc_id": "doc-b",
                "role_id": "role-sales",
                "role_ids": ["role-sales"],
                "chunk_id": "doc-b:1:0000",
            },
        )
    ]

    plan = plan_qdrant_payload_migration(points)
    assert plan.updates == ()


def test_apply_updates_qdrant_payloads() -> None:
    points = [
        QdrantPointRecord(
            point_id="p1",
            payload={"doc_id": "doc-c", "role_id": "role-sales", "text": "a"},
        ),
        QdrantPointRecord(
            point_id="p2",
            payload={"doc_id": "doc-c", "role_id": "role-support", "text": "b"},
        ),
    ]
    client = FakeScrollClient(points)

    dry = apply_qdrant_payload_migration(client, "kb", dry_run=True)
    assert dry.applied is False
    assert client.payload_updates == []

    applied = apply_qdrant_payload_migration(client, "kb", dry_run=False)
    assert applied.applied is True
    assert applied.points_updated == 2
    assert len(client.payload_updates) == 2
    for _, payload, _ in client.payload_updates:
        assert payload["role_ids"] == ["role-sales", "role-support"]
