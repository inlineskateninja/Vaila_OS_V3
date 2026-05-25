from abc import ABC, abstractmethod
from typing import Any
from app.memory.models import MemoryRecord, MemoryCandidate


class MemoryBackend(ABC):
    @abstractmethod
    def load(self) -> None:
        """Initialise or reload the underlying memory storage/connection."""
        pass

    @abstractmethod
    def state_summary(self) -> dict:
        """Return a dictionary of state counters (records, candidates by status, etc.)."""
        pass

    @abstractmethod
    def create_candidate(self, candidate: MemoryCandidate) -> MemoryCandidate:
        """Persist a single MemoryCandidate."""
        pass

    @abstractmethod
    def create_candidates(self, candidates: list[MemoryCandidate]) -> list[MemoryCandidate]:
        """Persist multiple MemoryCandidate records."""
        pass

    @abstractmethod
    def list_candidates(self, status: str = "pending") -> list[MemoryCandidate]:
        """List persisted candidates filtered by their current status."""
        pass

    @abstractmethod
    def get_candidate(self, candidate_id: str) -> MemoryCandidate | None:
        """Retrieve a specific MemoryCandidate by ID."""
        pass

    @abstractmethod
    def approve_candidate(self, candidate_id: str) -> tuple[MemoryCandidate, Any]:
        """Approve a pending memory candidate, converting it to a MemoryRecord and returning both."""
        pass

    @abstractmethod
    def reject_candidate(self, candidate_id: str, note: str = "") -> MemoryCandidate:
        """Reject a pending memory candidate and store a review note."""
        pass

    @abstractmethod
    def search_memory(
        self,
        query: str,
        persona: str = "proto_jane",
        tags: list[str] | None = None,
        limit: int = 8,
        category: str | None = None,
    ) -> list[MemoryRecord]:
        """Perform a standard search query returning matching MemoryRecord list."""
        pass

    @abstractmethod
    def search_memory_scored(
        self,
        query: str,
        persona: str = "proto_jane",
        tags: list[str] | None = None,
        limit: int = 8,
        category: str | None = None,
    ) -> list[tuple[float, MemoryRecord]]:
        """Perform a scored search returning (float_score, MemoryRecord) tuples."""
        pass

    @abstractmethod
    def append_memory(self, record: MemoryRecord, relative_path: str | None = None) -> Any:
        """Directly write an approved MemoryRecord to persistent storage."""
        pass
