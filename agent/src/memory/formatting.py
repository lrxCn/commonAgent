"""Format user memory facts for system prompt injection."""

from __future__ import annotations


def format_user_memories_for_system(memories: list[str]) -> str:
    """Format memory facts for injection into the system prompt."""
    facts = [m.strip() for m in memories if m and m.strip()]
    if not facts:
        return ""
    lines = ["## User preferences (from memory)", ""]
    lines.extend(f"- {fact}" for fact in facts)
    return "\n".join(lines)
