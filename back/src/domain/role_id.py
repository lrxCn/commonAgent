"""Role id format validation for demo platform (reused by admin CRUD in task 86)."""

from __future__ import annotations

import re

ROLE_ID_PATTERN = re.compile(r"^role-[a-z0-9-]+$")


def is_valid_role_id(role_id: str) -> bool:
    return bool(ROLE_ID_PATTERN.fullmatch(role_id))


def validate_role_id(role_id: str) -> str:
    if not is_valid_role_id(role_id):
        raise ValueError(
            f"Invalid role_id {role_id!r}; expected format role-[a-z0-9-]+"
        )
    return role_id
