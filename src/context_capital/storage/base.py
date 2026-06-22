"""StoreBase — the abstract surface shared by SQLiteStore and PostgresStore."""
from __future__ import annotations

from abc import ABC, abstractmethod
from types import TracebackType
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from context_capital.ingest.types import IngestContext


class StoreBase(ABC):
    """Abstract storage interface implemented by SQLiteStore and PostgresStore."""

    # ---- Lifecycle --------------------------------------------------------
    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def close(self) -> None: ...

    def __enter__(self) -> "StoreBase":
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    # ---- Subjects ---------------------------------------------------------
    @abstractmethod
    def ensure_subject(
        self,
        subject_id: str,
        subject_type: str = "person",
        display_name: str | None = None,
    ) -> None: ...

    # ---- Memories ---------------------------------------------------------
    @abstractmethod
    def add_memory(self, memory: dict[str, Any], *, actor: str = "system") -> None: ...

    @abstractmethod
    def list_memories(
        self,
        *,
        subject_id: str | None = None,
        kind: str | None = None,
        sensitivity: list[str] | None = None,
    ) -> list[dict[str, Any]]: ...

    @abstractmethod
    def get_memory(self, memory_id: str) -> dict[str, Any] | None: ...

    # ---- Contexts ---------------------------------------------------------
    @abstractmethod
    def persist_ingest_context(
        self,
        ic: "IngestContext",
        *,
        subject_id: str,
        actor: str = "system",
    ) -> str: ...

    @abstractmethod
    def get_context_by_unique(
        self,
        subject_id: str,
        source_file_hash: str,
        vendor_conversation_id: str,
    ) -> dict[str, Any] | None: ...

    # ---- Audit ------------------------------------------------------------
    @abstractmethod
    def audit_log(self, limit: int = 100) -> list[dict[str, Any]]: ...

    # ---- Embeddings + semantic search (Postgres overrides) ---------------
    def supports_embeddings(self) -> bool:
        return False

    def add_embedding(
        self,
        memory_id: str,
        vector: list[float],
        *,
        model: str,
    ) -> None:
        """Default no-op. Subclasses with vector storage override."""

    def search_by_embedding(
        self,
        vector: list[float],
        *,
        limit: int = 10,
        subject_id: str | None = None,
        kind: str | None = None,
        sensitivity: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError(
            "semantic search requires the Postgres backend; "
            "set CC_DATABASE_URL=postgresql://..."
        )
