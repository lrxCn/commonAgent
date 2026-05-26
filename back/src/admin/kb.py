"""Admin KB document service: Back meta + Agent ingest/list/delete."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, exists, func, or_, select
from sqlalchemy.orm import Session

from api.errors import conflict, not_found
from db.models import KbDocumentMeta, KbDocumentRole, Role
from services.agent_kb import (
    agent_kb_delete_document,
    agent_kb_get_document,
    agent_kb_ingest,
)

MAX_KB_CONTENT_BYTES = 2 * 1024 * 1024


def _new_doc_id() -> str:
    return f"doc-{uuid.uuid4().hex[:12]}"


def _normalize_role_ids(role_ids: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in role_ids:
        rid = raw.strip()
        if not rid or rid in seen:
            continue
        seen.add(rid)
        normalized.append(rid)
    return normalized


def _validate_role_ids(db: Session, role_ids: list[str]) -> list[str]:
    ids = _normalize_role_ids(role_ids)
    if not ids:
        raise conflict(
            "role_ids 不能为空",
            field_errors={"role_ids": "至少需要一个角色"},
        )
    for rid in ids:
        if db.get(Role, rid) is None:
            raise not_found(f"角色不存在：{rid}")
    return ids


def _validate_content_bytes(content: str) -> str:
    body = content.strip()
    if not body:
        raise conflict("文档内容不能为空", field_errors={"content": "不能为空"})
    encoded = body.encode("utf-8")
    if len(encoded) > MAX_KB_CONTENT_BYTES:
        raise conflict(
            "文档大小不能超过 2MB",
            field_errors={"content": "超过 2MB 限制"},
        )
    return body


def _role_ids_for_doc(db: Session, doc_id: str) -> list[str]:
    rows = db.scalars(
        select(KbDocumentRole.role_id)
        .where(KbDocumentRole.doc_id == doc_id)
        .order_by(KbDocumentRole.role_id.asc())
    ).all()
    return list(rows)


def _role_ids_map(db: Session, doc_ids: list[str]) -> dict[str, list[str]]:
    if not doc_ids:
        return {}
    rows = db.execute(
        select(KbDocumentRole.doc_id, KbDocumentRole.role_id)
        .where(KbDocumentRole.doc_id.in_(doc_ids))
        .order_by(KbDocumentRole.doc_id.asc(), KbDocumentRole.role_id.asc())
    ).all()
    mapping: dict[str, list[str]] = {doc_id: [] for doc_id in doc_ids}
    for doc_id, role_id in rows:
        mapping[doc_id].append(role_id)
    return mapping


def _meta_to_dict(row: KbDocumentMeta, *, role_ids: list[str]) -> dict[str, object]:
    return {
        "doc_id": row.doc_id,
        "role_ids": role_ids,
        "doc_name": row.doc_name,
        "version": row.version,
        "raw_content": row.raw_content,
        "chunks_written": row.chunks_written,
        "tokens_estimated": row.tokens_estimated,
        "created_by": row.created_by,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _replace_role_bindings(db: Session, doc_id: str, role_ids: list[str]) -> None:
    db.execute(delete(KbDocumentRole).where(KbDocumentRole.doc_id == doc_id))
    for rid in role_ids:
        db.add(KbDocumentRole(doc_id=doc_id, role_id=rid))


def list_documents(
    db: Session,
    *,
    role_id: str | None = None,
    keyword: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> dict[str, object]:
    filters = []
    if role_id and role_id.strip():
        rid = role_id.strip()
        filters.append(
            exists().where(
                KbDocumentRole.doc_id == KbDocumentMeta.doc_id,
                KbDocumentRole.role_id == rid,
            )
        )
    if keyword and keyword.strip():
        pattern = f"%{keyword.strip()}%"
        filters.append(
            or_(
                KbDocumentMeta.doc_name.ilike(pattern),
                KbDocumentMeta.doc_id.ilike(pattern),
            )
        )

    count_query = select(func.count()).select_from(KbDocumentMeta)
    list_query = select(KbDocumentMeta).order_by(
        KbDocumentMeta.updated_at.desc(),
        KbDocumentMeta.doc_name.asc(),
    )
    for clause in filters:
        count_query = count_query.where(clause)
        list_query = list_query.where(clause)

    total = db.scalar(count_query) or 0
    rows = db.scalars(list_query.offset(offset).limit(limit)).all()
    role_map = _role_ids_map(db, [row.doc_id for row in rows])
    return {
        "items": [
            _meta_to_dict(row, role_ids=role_map.get(row.doc_id, [])) for row in rows
        ],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


def get_document(db: Session, doc_id: str) -> dict[str, object]:
    row = db.get(KbDocumentMeta, doc_id.strip())
    if row is None:
        raise not_found("文档不存在")

    detail = agent_kb_get_document(doc_id)
    role_ids = _role_ids_for_doc(db, row.doc_id)
    payload = _meta_to_dict(row, role_ids=role_ids)
    payload["chunks"] = detail.get("chunks", [])
    return payload


def create_document(
    db: Session,
    *,
    role_ids: list[str],
    doc_name: str,
    content: str,
    created_by: str,
    doc_id: str | None = None,
    version: str = "1",
) -> dict[str, object]:
    rids = _validate_role_ids(db, role_ids)
    body = _validate_content_bytes(content)
    name = doc_name.strip()
    if not name:
        raise conflict("doc_name 不能为空", field_errors={"doc_name": "不能为空"})

    did = (doc_id or _new_doc_id()).strip()
    ver = version.strip() or "1"
    if db.get(KbDocumentMeta, did) is not None:
        raise conflict(
            "文档已存在",
            field_errors={"doc_id": "doc_id 已占用"},
        )

    ingest_result = agent_kb_ingest(
        {
            "role_ids": rids,
            "doc_id": did,
            "doc_name": name,
            "version": ver,
            "content": body,
        }
    )

    row = KbDocumentMeta(
        doc_id=did,
        doc_name=name,
        version=ingest_result["version"],
        raw_content=body,
        chunks_written=int(ingest_result["chunks_written"]),
        tokens_estimated=int(ingest_result["tokens_estimated"]),
        created_by=created_by,
    )
    db.add(row)
    db.flush()
    _replace_role_bindings(db, did, rids)
    db.commit()
    db.refresh(row)
    return _meta_to_dict(row, role_ids=rids)


def update_document(
    db: Session,
    doc_id: str,
    *,
    role_ids: list[str] | None = None,
    doc_name: str | None = None,
    raw_content: str | None = None,
    version: str | None = None,
) -> dict[str, object]:
    row = db.get(KbDocumentMeta, doc_id.strip())
    if row is None:
        raise not_found("文档不存在")

    current_role_ids = _role_ids_for_doc(db, row.doc_id)
    next_role_ids = _validate_role_ids(db, role_ids) if role_ids is not None else current_role_ids

    name = doc_name.strip() if doc_name is not None else row.doc_name
    if not name:
        raise conflict("doc_name 不能为空", field_errors={"doc_name": "不能为空"})

    body = _validate_content_bytes(raw_content if raw_content is not None else row.raw_content)
    ver = (version or row.version).strip() or row.version

    ingest_result = agent_kb_ingest(
        {
            "role_ids": next_role_ids,
            "doc_id": row.doc_id,
            "doc_name": name,
            "version": ver,
            "content": body,
        }
    )

    row.doc_name = name
    row.version = ingest_result["version"]
    row.raw_content = body
    row.chunks_written = int(ingest_result["chunks_written"])
    row.tokens_estimated = int(ingest_result["tokens_estimated"])
    _replace_role_bindings(db, row.doc_id, next_role_ids)
    db.commit()
    db.refresh(row)
    return _meta_to_dict(row, role_ids=next_role_ids)


def delete_document(db: Session, doc_id: str) -> None:
    row = db.get(KbDocumentMeta, doc_id.strip())
    if row is None:
        raise not_found("文档不存在")

    agent_kb_delete_document(doc_id)
    db.delete(row)
    db.commit()
