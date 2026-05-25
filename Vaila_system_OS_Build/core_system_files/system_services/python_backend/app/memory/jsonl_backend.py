from pathlib import Path
from typing import Any

from app.memory_store import MemoryStore
from app.candidate_store import CandidateStore
from app.memory.backend import MemoryBackend
from app.memory.models import MemoryRecord, MemoryCandidate


class JsonlMemoryBackend(MemoryBackend):
    def __init__(self, memory_root: str | Path, candidate_root: str | Path):
        self.memory_store = MemoryStore(memory_root)
        self.candidate_store = CandidateStore(candidate_root)

    def load(self) -> None:
        self.memory_store.load()
        self.candidate_store.load()

    def state_summary(self) -> dict:
        return {
            "memory_records": len(self.memory_store.records),
            "memory_categories": self.memory_store.category_counts(),
            "memory_recency": self.memory_store.recency_counts(),
            "pending_candidates": len(self.candidate_store.list_candidates("pending")),
            "approved_candidates": len(self.candidate_store.list_candidates("approved")),
            "rejected_candidates": len(self.candidate_store.list_candidates("rejected")),
        }

    def create_candidate(self, candidate: MemoryCandidate) -> MemoryCandidate:
        added = self.candidate_store.add_many([candidate])
        if not added:
            existing = self.candidate_store.get(candidate.id)
            if existing:
                return existing
        return candidate

    def create_candidates(self, candidates: list[MemoryCandidate]) -> list[MemoryCandidate]:
        return self.candidate_store.add_many(candidates)

    def list_candidates(self, status: str = "pending") -> list[MemoryCandidate]:
        return self.candidate_store.list_candidates(status)

    def get_candidate(self, candidate_id: str) -> MemoryCandidate | None:
        return self.candidate_store.get(candidate_id)

    def approve_candidate(self, candidate_id: str) -> tuple[MemoryCandidate, Any]:
        return self.candidate_store.approve(candidate_id, self.memory_store)

    def reject_candidate(self, candidate_id: str, note: str = "") -> MemoryCandidate:
        return self.candidate_store.reject(candidate_id, note=note)

    def search_memory(
        self,
        query: str,
        persona: str = "proto_jane",
        tags: list[str] | None = None,
        limit: int = 8,
        category: str | None = None,
    ) -> list[MemoryRecord]:
        return self.memory_store.search(
            query=query,
            persona=persona,
            tags=tags,
            limit=limit,
            category=category,
        )

    def search_memory_scored(
        self,
        query: str,
        persona: str = "proto_jane",
        tags: list[str] | None = None,
        limit: int = 8,
        category: str | None = None,
    ) -> list[tuple[float, MemoryRecord]]:
        return self.memory_store.search_scored(
            query=query,
            persona=persona,
            tags=tags,
            limit=limit,
            category=category,
        )

    def append_memory(self, record: MemoryRecord, relative_path: str | None = None) -> Any:
        return self.memory_store.append_record(record, relative_path=relative_path)
