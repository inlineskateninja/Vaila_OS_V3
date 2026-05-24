import json
from datetime import datetime, timezone
from pathlib import Path

from app.memory_store import MemoryStore
from app.schemas import MemoryCandidate


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class CandidateStore:
    def __init__(self, store_root: str | Path):
        self.store_root = Path(store_root)
        self.pending_path = self.store_root / "pending.jsonl"
        self.reviewed_path = self.store_root / "reviewed.jsonl"
        self.candidates: list[MemoryCandidate] = []

    def load(self) -> None:
        self.store_root.mkdir(parents=True, exist_ok=True)
        self.candidates.clear()
        self._load_file(self.pending_path)
        self._load_file(self.reviewed_path)

    def _load_file(self, path: Path) -> None:
        if not path.exists():
            return

        with path.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    self.candidates.append(MemoryCandidate.from_dict(json.loads(line)))
                except json.JSONDecodeError as error:
                    print(f"Skipping invalid candidate JSON in {path}, line {line_number}: {error}")

    def add_many(self, candidates: list[MemoryCandidate]) -> list[MemoryCandidate]:
        self.store_root.mkdir(parents=True, exist_ok=True)
        existing_ids = {candidate.id for candidate in self.candidates}
        added: list[MemoryCandidate] = []

        with self.pending_path.open("a", encoding="utf-8") as file:
            for candidate in candidates:
                if candidate.id in existing_ids:
                    continue
                candidate.status = "pending"
                file.write(json.dumps(candidate.to_dict(), ensure_ascii=False) + "\n")
                self.candidates.append(candidate)
                existing_ids.add(candidate.id)
                added.append(candidate)

        return added

    def list_candidates(self, status: str | None = "pending") -> list[MemoryCandidate]:
        if status is None or status == "all":
            return list(self.candidates)
        return [candidate for candidate in self.candidates if candidate.status == status]

    def get(self, candidate_id: str) -> MemoryCandidate | None:
        for candidate in self.candidates:
            if candidate.id == candidate_id:
                return candidate
        return None

    def approve(self, candidate_id: str, memory_store: MemoryStore) -> tuple[MemoryCandidate, Path]:
        candidate = self.get(candidate_id)
        if candidate is None:
            raise KeyError(f"Unknown candidate: {candidate_id}")
        if candidate.status != "pending":
            raise ValueError(f"Candidate is not pending: {candidate_id} ({candidate.status})")

        reviewed_at = utc_now()
        record = candidate.to_memory_record(approved_at=reviewed_at)
        target_path = memory_store.append_record(record)
        candidate.status = "approved"
        candidate.reviewed_at = reviewed_at
        self._rewrite_files()
        return candidate, target_path

    def reject(self, candidate_id: str, note: str = "") -> MemoryCandidate:
        candidate = self.get(candidate_id)
        if candidate is None:
            raise KeyError(f"Unknown candidate: {candidate_id}")
        if candidate.status != "pending":
            raise ValueError(f"Candidate is not pending: {candidate_id} ({candidate.status})")

        candidate.status = "rejected"
        candidate.reviewed_at = utc_now()
        candidate.review_note = note
        self._rewrite_files()
        return candidate

    def _rewrite_files(self) -> None:
        self.store_root.mkdir(parents=True, exist_ok=True)
        pending = [candidate for candidate in self.candidates if candidate.status == "pending"]
        reviewed = [candidate for candidate in self.candidates if candidate.status != "pending"]
        self._write_jsonl(self.pending_path, pending)
        self._write_jsonl(self.reviewed_path, reviewed)

    @staticmethod
    def _write_jsonl(path: Path, candidates: list[MemoryCandidate]) -> None:
        with path.open("w", encoding="utf-8") as file:
            for candidate in candidates:
                file.write(json.dumps(candidate.to_dict(), ensure_ascii=False) + "\n")
