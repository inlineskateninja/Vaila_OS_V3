import json
from pathlib import Path
from typing import Any

from app.memory.backend import MemoryBackend
from app.memory.jsonl_backend import JsonlMemoryBackend
from app.memory.sqlite_backend import SQLiteMemoryBackend
from app.memory.models import MemoryRecord, MemoryCandidate
from app.paths import get_vaila_paths

DEFAULT_CONFIG = {
    "backend": "jsonl",
    "sqlite_path": "data/vaila_memory.sqlite3",
    "vector_backend": "none",
    "external_memory": "none",
    "embedding_provider": "none",
    "embedding_model": "",
    "embedding_dimensions": 0
}

def get_config_path(project_root: str | Path) -> Path:
    return Path(project_root) / "data" / "memory_config.json"

def save_default_memory_config_if_missing(project_root: str | Path) -> None:
    config_path = get_config_path(project_root)
    if not config_path.exists():
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with config_path.open("w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)

def load_memory_config(project_root: str | Path) -> dict[str, Any]:
    config_path = get_config_path(project_root)
    save_default_memory_config_if_missing(project_root)
    with config_path.open("r", encoding="utf-8") as f:
        return json.load(f)

def build_memory_backend(project_root: str | Path, config: dict[str, Any]) -> MemoryBackend:
    backend_type = config.get("backend", "jsonl")
    if backend_type == "jsonl":
        paths = get_vaila_paths(project_root)
        return JsonlMemoryBackend(paths.memory_root, paths.candidate_root)
    elif backend_type == "sqlite":
        sqlite_path_str = config.get("sqlite_path", "data/vaila_memory.sqlite3")
        sqlite_path = Path(sqlite_path_str)
        if not sqlite_path.is_absolute():
            sqlite_path = Path(project_root) / sqlite_path
        return SQLiteMemoryBackend(sqlite_path)
    else:
        raise ValueError(f"Invalid backend: {backend_type}. Supported: jsonl, sqlite")


class MemoryStoreAdapter:
    def __init__(self, backend: MemoryBackend):
        self._backend = backend

    @property
    def records(self) -> list[MemoryRecord]:
        if hasattr(self._backend, "memory_store"):
            return self._backend.memory_store.records
        if hasattr(self._backend, "conn") and self._backend.conn:
            cursor = self._backend.conn.cursor()
            cursor.execute("SELECT raw_json FROM memory_items")
            rows = cursor.fetchall()
            return [MemoryRecord.from_dict(json.loads(row[0])) for row in rows]
        return []

    def category_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for record in self.records:
            counts[record.category] = counts.get(record.category, 0) + 1
        return dict(sorted(counts.items()))

    def recency_counts(self) -> dict[str, int]:
        from app.memory_store import recency_bucket
        counts: dict[str, int] = {}
        for record in self.records:
            bucket = recency_bucket(record)
            counts[bucket] = counts.get(bucket, 0) + 1
        return dict(sorted(counts.items()))


class CandidateStoreAdapter:
    def __init__(self, backend: MemoryBackend):
        self._backend = backend

    def list_candidates(self, status: str = "pending") -> list[MemoryCandidate]:
        return self._backend.list_candidates(status)

    def get(self, candidate_id: str) -> MemoryCandidate | None:
        return self._backend.get_candidate(candidate_id)

    def add_many(self, candidates: list[MemoryCandidate]) -> list[MemoryCandidate]:
        return self._backend.create_candidates(candidates)
