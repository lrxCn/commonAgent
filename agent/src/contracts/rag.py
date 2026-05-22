"""RAG contracts shared by retriever, context assembly, and graph state."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

RagChannel = Literal["dense", "text", "bm25", "mock"]


@dataclass(frozen=True)
class RagChunk:
    """Single retrieved knowledge chunk with citation identifiers."""

    doc_id: str
    chunk_id: str
    text: str
    score: float
    channel: RagChannel | None = None
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        if self.channel is None:
            data.pop("channel")
        if self.metadata is None:
            data.pop("metadata")
        return data


@dataclass(frozen=True)
class RagResult:
    """Typed RAG retrieval result for future service boundaries."""

    chunks: tuple[RagChunk, ...]
    query: str
    role_id: str
    skipped: bool = False
    second_pass: bool = False
    dense_count: int = 0
    sparse_count: int = 0
    reranked_count: int = 0
    mock: bool = False

    @classmethod
    def from_chunks(
        cls,
        chunks: list[RagChunk],
        *,
        query: str,
        role_id: str,
        skipped: bool = False,
        second_pass: bool = False,
        dense_count: int = 0,
        sparse_count: int = 0,
        reranked_count: int | None = None,
        mock: bool = False,
    ) -> "RagResult":
        return cls(
            chunks=tuple(chunks),
            query=query,
            role_id=role_id,
            skipped=skipped,
            second_pass=second_pass,
            dense_count=dense_count,
            sparse_count=sparse_count,
            reranked_count=len(chunks) if reranked_count is None else reranked_count,
            mock=mock,
        )
