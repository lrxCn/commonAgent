"""Student CRUD service — shared table for all authenticated users."""

from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.errors import conflict, not_found
from db.models import Student

STUDENT_STATUSES = frozenset({"active", "inactive"})


def _new_student_id() -> str:
    return f"s-{uuid.uuid4().hex[:12]}"


def student_to_dict(student: Student) -> dict[str, object]:
    return {
        "student_id": student.student_id,
        "student_no": student.student_no,
        "name": student.name,
        "class_name": student.class_name,
        "status": student.status,
        "created_at": student.created_at,
        "updated_at": student.updated_at,
    }


def list_students(
    db: Session,
    *,
    offset: int = 0,
    limit: int = 20,
    search: str | None = None,
    status: str | None = None,
    class_name: str | None = None,
) -> tuple[list[Student], int]:
    query = select(Student)
    count_query = select(func.count()).select_from(Student)

    if search and search.strip():
        term = f"%{search.strip()}%"
        search_filter = or_(
            Student.name.ilike(term),
            Student.student_no.ilike(term),
            Student.class_name.ilike(term),
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    if status and status.strip():
        query = query.where(Student.status == status.strip())
        count_query = count_query.where(Student.status == status.strip())

    if class_name and class_name.strip():
        query = query.where(Student.class_name == class_name.strip())
        count_query = count_query.where(Student.class_name == class_name.strip())

    total = db.scalar(count_query) or 0
    rows = db.scalars(
        query.order_by(Student.student_no.asc()).offset(offset).limit(limit)
    ).all()
    return list(rows), int(total)


def get_student(db: Session, student_id: str) -> Student:
    student = db.get(Student, student_id)
    if student is None:
        raise not_found("学生不存在")
    return student


def _validate_status(status: str | None) -> str:
    if status is None:
        return "active"
    normalized = status.strip()
    if normalized not in STUDENT_STATUSES:
        raise ValueError(f"status must be one of: {', '.join(sorted(STUDENT_STATUSES))}")
    return normalized


def create_student(
    db: Session,
    *,
    student_no: str,
    name: str,
    class_name: str | None,
    status: str | None,
    created_by: str,
) -> Student:
    student = Student(
        student_id=_new_student_id(),
        student_no=student_no.strip(),
        name=name.strip(),
        class_name=class_name.strip() if class_name and class_name.strip() else None,
        status=_validate_status(status),
        created_by=created_by,
    )
    db.add(student)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("学号已存在", field_errors={"student_no": "已占用"}) from exc
    db.refresh(student)
    return student


def update_student(
    db: Session,
    student_id: str,
    updates: dict[str, object],
) -> Student:
    if not updates:
        return get_student(db, student_id)

    student = get_student(db, student_id)

    if "student_no" in updates and updates["student_no"] is not None:
        student.student_no = str(updates["student_no"]).strip()
    if "name" in updates and updates["name"] is not None:
        student.name = str(updates["name"]).strip()
    if "class_name" in updates:
        raw = updates["class_name"]
        if raw is None or not str(raw).strip():
            student.class_name = None
        else:
            student.class_name = str(raw).strip()
    if "status" in updates and updates["status"] is not None:
        student.status = _validate_status(str(updates["status"]))

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("学号已存在", field_errors={"student_no": "已占用"}) from exc
    db.refresh(student)
    return student


def delete_student(db: Session, student_id: str) -> None:
    student = get_student(db, student_id)
    db.delete(student)
    db.commit()


def batch_delete_students(db: Session, student_ids: list[str]) -> int:
    if not student_ids:
        return 0
    unique_ids = list(dict.fromkeys(student_ids))
    rows = db.scalars(
        select(Student).where(Student.student_id.in_(unique_ids))
    ).all()
    for row in rows:
        db.delete(row)
    db.commit()
    return len(rows)


def list_distinct_class_names(db: Session) -> list[str]:
    rows = db.scalars(
        select(Student.class_name)
        .where(Student.class_name.is_not(None))
        .distinct()
        .order_by(Student.class_name.asc())
    ).all()
    return [name for name in rows if name]
