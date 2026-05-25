from abc import ABC, abstractmethod
from typing import Any

class VectorMemoryBackend(ABC):
    @abstractmethod
    def upsert_memory(self, memory_id: str, text: str, metadata: dict[str, Any]) -> None:
        pass

    @abstractmethod
    def delete_memory(self, memory_id: str) -> None:
        pass

    @abstractmethod
    def search(self, query_vector: list[float], filters: dict[str, Any] | None = None, limit: int = 8) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    def health(self) -> dict[str, Any]:
        pass


class NullVectorMemoryBackend(VectorMemoryBackend):
    def upsert_memory(self, memory_id: str, text: str, metadata: dict[str, Any]) -> None:
        pass

    def delete_memory(self, memory_id: str) -> None:
        pass

    def search(self, query_vector: list[float], filters: dict[str, Any] | None = None, limit: int = 8) -> list[dict[str, Any]]:
        return []

    def health(self) -> dict[str, Any]:
        return {
            "status": "disabled",
            "backend": "none",
            "connected": False
        }
