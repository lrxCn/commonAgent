"""Role CRUD service for admin API."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.errors import conflict, not_found
from db.models import KbDocumentRole, Role, UserRole
from domain.role_id import validate_role_id


def role_to_dict(
    role: Role,
    *,
    user_count: int = 0,
    document_count: int = 0,
) -> dict[str, object]:
    return {
        "role_id": role.role_id,
        "name": role.name,
        "description": role.description,
        "user_count": user_count,
        "document_count": document_count,
        "created_at": role.created_at,
        "updated_at": role.updated_at,
    }


def _user_counts(db: Session) -> dict[str, int]:
    rows = db.execute(
        select(UserRole.role_id, func.count(UserRole.user_id))
        .group_by(UserRole.role_id)
    ).all()
    return {role_id: int(count) for role_id, count in rows}


def _document_counts(db: Session) -> dict[str, int]:
    rows = db.execute(
        select(KbDocumentRole.role_id, func.count(func.distinct(KbDocumentRole.doc_id)))
        .group_by(KbDocumentRole.role_id)
    ).all()
    return {role_id: int(count) for role_id, count in rows}


def list_roles(db: Session) -> list[dict[str, object]]:
    user_counts = _user_counts(db)
    doc_counts = _document_counts(db)
    roles = db.scalars(select(Role).order_by(Role.role_id.asc())).all()
    return [
        role_to_dict(
            role,
            user_count=user_counts.get(role.role_id, 0),
            document_count=doc_counts.get(role.role_id, 0),
        )
        for role in roles
    ]


def get_role(db: Session, role_id: str) -> dict[str, object]:
    role = db.get(Role, role_id)
    if role is None:
        raise not_found("角色不存在")
    user_count = db.scalar(
        select(func.count()).select_from(UserRole).where(UserRole.role_id == role_id)
    ) or 0
    document_count = db.scalar(
        select(func.count(func.distinct(KbDocumentRole.doc_id)))
        .select_from(KbDocumentRole)
        .where(KbDocumentRole.role_id == role_id)
    ) or 0
    return role_to_dict(
        role,
        user_count=int(user_count),
        document_count=int(document_count),
    )


def create_role(
    db: Session,
    *,
    role_id: str,
    name: str,
    description: str | None,
) -> dict[str, object]:
    try:
        validate_role_id(role_id.strip())
    except ValueError as exc:
        raise conflict(str(exc), field_errors={"role_id": "格式无效"}) from exc

    role = Role(
        role_id=role_id.strip(),
        name=name.strip(),
        description=description.strip() if description and description.strip() else None,
    )
    db.add(role)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("角色 ID 已存在", field_errors={"role_id": "已占用"}) from exc
    db.refresh(role)
    return role_to_dict(role)


def update_role(
    db: Session,
    role_id: str,
    updates: dict[str, object],
) -> dict[str, object]:
    role = db.get(Role, role_id)
    if role is None:
        raise not_found("角色不存在")

    if "name" in updates and updates["name"] is not None:
        role.name = str(updates["name"]).strip()
    if "description" in updates:
        raw = updates["description"]
        if raw is None or not str(raw).strip():
            role.description = None
        else:
            role.description = str(raw).strip()

    db.commit()
    db.refresh(role)
    return get_role(db, role_id)


def delete_role(db: Session, role_id: str) -> None:
    role = db.get(Role, role_id)
    if role is None:
        raise not_found("角色不存在")

    user_count = db.scalar(
        select(func.count()).select_from(UserRole).where(UserRole.role_id == role_id)
    ) or 0
    if user_count > 0:
        raise conflict(
            "仍有用户绑定该角色，请先解绑",
            field_errors={"role_id": f"绑定用户数：{user_count}"},
        )

    document_count = db.scalar(
        select(func.count(func.distinct(KbDocumentRole.doc_id)))
        .select_from(KbDocumentRole)
        .where(KbDocumentRole.role_id == role_id)
    ) or 0
    if document_count > 0:
        raise conflict(
            "仍有知识库文档归属该角色，请先删除文档",
            field_errors={"role_id": f"文档数：{document_count}"},
        )

    db.delete(role)
    db.commit()
