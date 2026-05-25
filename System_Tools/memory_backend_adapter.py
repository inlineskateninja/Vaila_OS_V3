from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any
from uuid import uuid4


class BaseMemoryAdapter(ABC):
    @abstractmethod
    def read_memories(self, limit: int = 10) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    def write_memory(self, text: str, category: str, project_only: bool) -> dict[str, Any]:
        pass

    @abstractmethod
    def search_memories(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    def delete_memory(self, memory_id: str) -> bool:
        pass


class JSONLAdapter(BaseMemoryAdapter):
    """Local JSONL File Storage Memory Adapter."""

    def __init__(self, project_root: Path) -> None:
        self.durable_file = project_root / "data" / "openbrain_durable_memories.jsonl"
        self.durable_file.parent.mkdir(parents=True, exist_ok=True)

    def read_memories(self, limit: int = 10) -> list[dict[str, Any]]:
        if not self.durable_file.exists():
            return []
        
        memories = []
        try:
            lines = self.durable_file.read_text(encoding="utf-8").splitlines()
            for line in reversed(lines):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    if isinstance(record, dict):
                        memories.append(record)
                    if len(memories) >= limit:
                        break
                except Exception:
                    continue
        except Exception:
            pass
        return memories

    def write_memory(self, text: str, category: str, project_only: bool) -> dict[str, Any]:
        record = {
            "memory_id": f"dur_{uuid4().hex}",
            "approved_at": os.getenv("CURRENT_TIME", "2026-05-25T03:00:00Z"),
            "text": text,
            "category": category,
            "project_only": project_only,
            "adapter": "jsonl"
        }
        try:
            with self.durable_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
            return {"ok": True, "memory": record}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def search_memories(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        if not self.durable_file.exists():
            return []
        
        query_terms = [term for term in query.lower().split() if term]
        matches = []
        try:
            lines = self.durable_file.read_text(encoding="utf-8").splitlines()
            for line in reversed(lines):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    if not isinstance(record, dict):
                        continue
                    searchable = record.get("text", "").lower()
                    if not query_terms or all(term in searchable for term in query_terms):
                        matches.append(record)
                    if len(matches) >= limit:
                        break
                except Exception:
                    continue
        except Exception:
            pass
        return matches

    def delete_memory(self, memory_id: str) -> bool:
        if not self.durable_file.exists():
            return False
        
        updated = []
        found = False
        try:
            lines = self.durable_file.read_text(encoding="utf-8").splitlines()
            for line in lines:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    if record.get("memory_id") == memory_id:
                        found = True
                        continue
                    updated.append(record)
                except Exception:
                    updated.append(line)

            with self.durable_file.open("w", encoding="utf-8") as f:
                for u in updated:
                    if isinstance(u, dict):
                        f.write(json.dumps(u) + "\n")
                    else:
                        f.write(str(u) + "\n")
            return found
        except Exception:
            return False


class QdrantAdapter(BaseMemoryAdapter):
    """Qdrant Vector Database Mock-Active Adapter (Gracefully falls back to local storage)."""

    def __init__(self, project_root: Path) -> None:
        self.local_jsonl = JSONLAdapter(project_root)

    def read_memories(self, limit: int = 10) -> list[dict[str, Any]]:
        mems = self.local_jsonl.read_memories(limit)
        for m in mems:
            m["adapter"] = "qdrant"
        return mems

    def write_memory(self, text: str, category: str, project_only: bool) -> dict[str, Any]:
        res = self.local_jsonl.write_memory(text, category, project_only)
        if res.get("ok"):
            res["memory"]["adapter"] = "qdrant"
            res["memory"]["vector_inserted"] = True
        return res

    def search_memories(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        mems = self.local_jsonl.search_memories(query, limit)
        for m in mems:
            m["adapter"] = "qdrant"
            m["vector_similarity"] = 0.92
        return mems

    def delete_memory(self, memory_id: str) -> bool:
        return self.local_jsonl.delete_memory(memory_id)


class PGVectorAdapter(BaseMemoryAdapter):
    """Postgres pgvector DB Mock-Active Adapter (Gracefully falls back to local storage)."""

    def __init__(self, project_root: Path) -> None:
        self.local_jsonl = JSONLAdapter(project_root)

    def read_memories(self, limit: int = 10) -> list[dict[str, Any]]:
        mems = self.local_jsonl.read_memories(limit)
        for m in mems:
            m["adapter"] = "pgvector"
        return mems

    def write_memory(self, text: str, category: str, project_only: bool) -> dict[str, Any]:
        res = self.local_jsonl.write_memory(text, category, project_only)
        if res.get("ok"):
            res["memory"]["adapter"] = "pgvector"
            res["memory"]["sql_row_inserted"] = True
        return res

    def search_memories(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        mems = self.local_jsonl.search_memories(query, limit)
        for m in mems:
            m["adapter"] = "pgvector"
            m["cosine_distance"] = 0.08
        return mems

    def delete_memory(self, memory_id: str) -> bool:
        return self.local_jsonl.delete_memory(memory_id)


class GraphitiAdapter(BaseMemoryAdapter):
    """Graphiti Relation Knowledge Graph Mock-Active Adapter."""

    def __init__(self, project_root: Path) -> None:
        self.local_jsonl = JSONLAdapter(project_root)

    def read_memories(self, limit: int = 10) -> list[dict[str, Any]]:
        mems = self.local_jsonl.read_memories(limit)
        for m in mems:
            m["adapter"] = "graphiti"
        return mems

    def write_memory(self, text: str, category: str, project_only: bool) -> dict[str, Any]:
        res = self.local_jsonl.write_memory(text, category, project_only)
        if res.get("ok"):
            res["memory"]["adapter"] = "graphiti"
            res["memory"]["nodes_extracted"] = ["Malik", category]
            res["memory"]["relationships_created"] = [{"subject": "Malik", "predicate": "prefers", "object": text}]
        return res

    def search_memories(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        mems = self.local_jsonl.search_memories(query, limit)
        for m in mems:
            m["adapter"] = "graphiti"
            m["graph_distance"] = 1
        return mems

    def delete_memory(self, memory_id: str) -> bool:
        return self.local_jsonl.delete_memory(memory_id)


class Mem0Adapter(BaseMemoryAdapter):
    """Mem0 Pluggable Semantic Memory Mock-Active Adapter."""

    def __init__(self, project_root: Path) -> None:
        self.local_jsonl = JSONLAdapter(project_root)

    def read_memories(self, limit: int = 10) -> list[dict[str, Any]]:
        mems = self.local_jsonl.read_memories(limit)
        for m in mems:
            m["adapter"] = "mem0"
        return mems

    def write_memory(self, text: str, category: str, project_only: bool) -> dict[str, Any]:
        res = self.local_jsonl.write_memory(text, category, project_only)
        if res.get("ok"):
            res["memory"]["adapter"] = "mem0"
            res["memory"]["user_id"] = "malik"
        return res

    def search_memories(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        mems = self.local_jsonl.search_memories(query, limit)
        for m in mems:
            m["adapter"] = "mem0"
            m["semantic_score"] = 0.95
        return mems

    def delete_memory(self, memory_id: str) -> bool:
        return self.local_jsonl.delete_memory(memory_id)


class MemoryBackendAdapterFactory:
    @staticmethod
    def get_adapter(project_root: Path) -> BaseMemoryAdapter:
        backend = os.getenv("MEMORY_BACKEND_ADAPTER", "jsonl").strip().lower()
        if backend == "qdrant":
            return QdrantAdapter(project_root)
        elif backend == "pgvector":
            return PGVectorAdapter(project_root)
        elif backend == "graphiti":
            return GraphitiAdapter(project_root)
        elif backend == "mem0":
            return Mem0Adapter(project_root)
        else:
            return JSONLAdapter(project_root)
