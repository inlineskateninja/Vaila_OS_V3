# Developer Note: Memory Architecture Plan

This document outlines the transition path for the Vaila Persona Core memory layer from our current offline-first, local JSONL store to an extensible, multi-backend adapter pattern.

## Current State: JSONL Memory Store

Currently, Vaila Persona Core uses an **in-memory** query and filtering model backed by two durable local storage components:
- **`MemoryStore` (`app/memory_store.py`):** Loads, searches, and appends `MemoryRecord` entries across category-based subfolders of `.jsonl` files in `system_wide_memory`.
- **`CandidateStore` (`app/candidate_store.py`):** Manages `pending.jsonl` and `reviewed.jsonl` files for the human-in-the-loop review and approval workflow.

This architecture is robust, zero-dependency, and extremely fast for local systems. It serves as our active, primary memory backend.

---

## Planned Architecture: The `MemoryBackend` Interface

To support scalable vector indices, graph databases, and external cloud memories without breaking our existing CLI and FastAPI endpoints, we will introduce a modular **`MemoryBackend` Interface** (Abstract Base Class).

```python
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any
from app.schemas import MemoryRecord

class MemoryBackend(ABC):
    @abstractmethod
    def load(self) -> None:
        """Initialise or reload the underlying memory storage/connection."""
        pass

    @abstractmethod
    def append_record(self, record: MemoryRecord, relative_path: str | None = None) -> Path:
        """Write a new approved MemoryRecord to the database/files."""
        pass

    @abstractmethod
    def search(
        self,
        query: str,
        persona: str = "proto_jane",
        tags: list[str] | None = None,
        limit: int = 5,
        category: str | None = None,
        prefer_recent: bool = True,
    ) -> list[MemoryRecord]:
        """Query memory records with relevancy, persona, and recency constraints."""
        pass
```

### Key Architectural Guidelines

1. **Current Backend Preservation:**
   - The current `MemoryStore` will be refactored as `JSONLMemoryBackend(MemoryBackend)`.
   - No existing JSONL files, pending/reviewed structures, or commands will be deleted or changed.
   
2. **Future Adapter Integrations:**
   - Database/graph engines (such as **Mem0**, **Graphiti**, **Qdrant**, **pgvector**, or standard **PostgreSQL**) will be developed as self-contained adapters implementing the `MemoryBackend` interface.
   - Core orchestrators like `VailaCore` (`app/core.py`) and FastAPI services (`app/service.py`) will load the appropriate backend dynamically based on `.env` configuration (e.g., `MEMORY_BACKEND_TYPE=jsonl`).

3. **Core Responsibility Separation:**
   - **Vaila Core remains the brain.** The individual storage backends are strictly adapters for storing and retrieving facts.
   - High-level cognitive features—such as memory approval/rejection workflows, persona scoping, fact extraction rules, and memory policy compliance—remain the exclusive responsibility of Vaila's core logic.

---

## Next Steps
1. Create the `MemoryBackend` interface under `app/memory_backend.py`.
2. Wrap `MemoryStore` as a subclass of `MemoryBackend`.
3. Configure `VailaCore` to construct the active backend dynamically.
4. Verify complete backward compatibility by running `pytest`.
