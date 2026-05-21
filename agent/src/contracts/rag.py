"""RAG contracts shared by retriever, context assembly, and graph state."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class RagChunk:
    """Single retrieved knowledge chunk with citation identifiers."""

    doc_id: str
    chunk_id: str
    text: str
    score: float

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class RagResult:
    """Typed RAG retrieval result for future service boundaries."""

    chunks: tuple[RagChunk, ...]
    query: str
    role_id: str
    skipped: bool = False
    second_pass: bool = False

    @classmethod
    def from_chunks(
        cls,
        chunks: list[RagChunk],
        *,
        query: str,
        role_id: str,
        skipped: bool = False,
        second_pass: bool = False,
    ) -> "RagResult":
        return cls(
            chunks=tuple(chunks),
            query=query,
            role_id=role_id,
            skipped=skipped,
            second_pass=second_pass,
        )
