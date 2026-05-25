from abc import ABC, abstractmethod

class EmbeddingProvider(ABC):
    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        pass

    @abstractmethod
    def embed_many(self, texts: list[str]) -> list[list[float]]:
        pass

    @abstractmethod
    def dimensions(self) -> int:
        pass

    @abstractmethod
    def provider_name(self) -> str:
        pass


class NullEmbeddingProvider(EmbeddingProvider):
    def embed_text(self, text: str) -> list[float]:
        return []

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        return [[] for _ in texts]

    def dimensions(self) -> int:
        return 0

    def provider_name(self) -> str:
        return "none"
