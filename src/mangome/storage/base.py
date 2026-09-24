from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class RevisionConflictError(RuntimeError):
    pass


class Store(ABC):
    @abstractmethod
    def insert(self, collection: str, doc: dict[str, Any]) -> dict[str, Any]: ...

    @abstractmethod
    def get(self, collection: str, entity_id: str) -> dict[str, Any] | None: ...

    @abstractmethod
    def find(self, collection: str, query: dict[str, Any] | None = None) -> list[dict[str, Any]]: ...

    def raw_find(self, collection: str) -> list[dict[str, Any]]:
        """Return persisted documents without reader-side schema upgrades."""
        return self.find(collection)

    @abstractmethod
    def update(
        self,
        collection: str,
        entity_id: str,
        patch: dict[str, Any],
        *,
        expected_revision: int | None = None,
    ) -> dict[str, Any]: ...

    @abstractmethod
    def ensure_indexes(self) -> None: ...

    def health(self) -> dict[str, Any]:
        return {"ok": True, "backend": self.__class__.__name__}
