from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Store(ABC):
    @abstractmethod
    def insert(self, collection: str, doc: dict[str, Any]) -> dict[str, Any]: ...

    @abstractmethod
    def get(self, collection: str, entity_id: str) -> dict[str, Any] | None: ...

    @abstractmethod
    def find(self, collection: str, query: dict[str, Any] | None = None) -> list[dict[str, Any]]: ...

    @abstractmethod
    def update(self, collection: str, entity_id: str, patch: dict[str, Any]) -> dict[str, Any]: ...

    @abstractmethod
    def ensure_indexes(self) -> None: ...
