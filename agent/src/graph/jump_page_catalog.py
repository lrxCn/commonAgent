"""jumpPage slug catalog for deterministic rule extraction (Back ToolSpec is prompt authority)."""

from __future__ import annotations

import re

JUMP_PAGE_SLUGS: frozenset[str] = frozenset(
    {"home", "students", "admin-roles", "admin-users", "admin-kb"}
)

JUMP_PAGE_CN_ALIASES: tuple[tuple[str, str], ...] = tuple(
    sorted(
        [
            ("角色管理", "admin-roles"),
            ("用户管理", "admin-users"),
            ("账号管理", "admin-users"),
            ("rag管理", "admin-kb"),
            ("RAG管理", "admin-kb"),
            ("知识库", "admin-kb"),
            ("文档管理", "admin-kb"),
            ("学生管理", "students"),
            ("学生列表", "students"),
            ("学生页", "students"),
            ("首页", "home"),
            ("主页", "home"),
            ("欢迎页", "home"),
        ],
        key=lambda item: len(item[0]),
        reverse=True,
    )
)

JUMP_PAGE_PATH_TO_SLUG: dict[str, str] = {
    "/app/home": "home",
    "/app/students": "students",
    "/app/admin/roles": "admin-roles",
    "/app/admin/users": "admin-users",
    "/app/admin/kb": "admin-kb",
}

_APP_PATH_RE = re.compile(r"(/app/[a-zA-Z0-9_\-/]+)", re.IGNORECASE)
_LEGACY_PAGE_RE = re.compile(r"(page[a-zA-Z0-9_\-]+)", re.IGNORECASE)
_LEGACY_PAGE_CN_RE = re.compile(r"页面\s*([a-zA-Z0-9_\-]+)", re.IGNORECASE)
_GENERIC_PATH_RE = re.compile(r"/([a-zA-Z0-9_\-/]+)")


def _text(value: str | None) -> str:
    return "" if value is None else str(value).strip()


def has_jump_page_reference(message: str) -> bool:
    """True when message mentions a catalog slug, alias, app path, or legacy page token."""
    text = _text(message)
    if not text:
        return False
    if extract_jump_page_slug(text):
        return True
    if _LEGACY_PAGE_RE.search(text):
        return True
    if _LEGACY_PAGE_CN_RE.search(text):
        return True
    if "订单页" in text:
        return True
    return _GENERIC_PATH_RE.search(text) is not None


def extract_jump_page_slug(message: str) -> str:
    """Map navigation text to a jumpPage slug, legacy page token, or path string."""
    text = _text(message)
    if not text:
        return ""

    for slug in sorted(JUMP_PAGE_SLUGS, key=len, reverse=True):
        if re.search(re.escape(slug), text, re.IGNORECASE):
            return slug

    text_lower = text.lower()
    for alias, slug in JUMP_PAGE_CN_ALIASES:
        if alias in text or alias.lower() in text_lower:
            return slug

    path_match = _APP_PATH_RE.search(text)
    if path_match:
        path = path_match.group(1).rstrip("/")
        for known_path, slug in JUMP_PAGE_PATH_TO_SLUG.items():
            if path.lower() == known_path.lower():
                return slug

    legacy = _LEGACY_PAGE_RE.search(text)
    if legacy:
        return legacy.group(1)

    legacy_cn = _LEGACY_PAGE_CN_RE.search(text)
    if legacy_cn:
        raw = legacy_cn.group(1)
        return raw if raw.lower().startswith("page") else f"page{raw}"

    generic = _GENERIC_PATH_RE.search(text)
    if generic:
        full = f"/{generic.group(1)}"
        for known_path, slug in JUMP_PAGE_PATH_TO_SLUG.items():
            if full.lower() == known_path.lower():
                return slug
        return full

    return ""
