from __future__ import annotations

import json
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.memory.config import (
    load_memory_config,
    save_default_memory_config_if_missing,
    build_memory_backend,
    MemoryStoreAdapter,
    CandidateStoreAdapter,
)
from app.memory.jsonl_backend import JsonlMemoryBackend
from app.memory.sqlite_backend import SQLiteMemoryBackend
from app.core import VailaCore
from app.service import app

def test_missing_config_creates_default_jsonl_config(tmp_path: Path) -> None:
    config_file = tmp_path / "data" / "memory_config.json"
    assert not config_file.exists()

    save_default_memory_config_if_missing(tmp_path)
    assert config_file.exists()

    with config_file.open("r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["backend"] == "jsonl"
    assert data["sqlite_path"] == "data/vaila_memory.sqlite3"
    assert data["vector_backend"] == "none"
    assert data["external_memory"] == "none"

def test_jsonl_config_builds_jsonl_memory_backend(tmp_path: Path) -> None:
    config = {
        "backend": "jsonl",
        "sqlite_path": "data/vaila_memory.sqlite3",
        "vector_backend": "none",
        "external_memory": "none"
    }
    backend = build_memory_backend(tmp_path, config)
    assert isinstance(backend, JsonlMemoryBackend)

def test_sqlite_config_builds_sqlite_memory_backend(tmp_path: Path) -> None:
    config = {
        "backend": "sqlite",
        "sqlite_path": "data/vaila_memory.sqlite3",
        "vector_backend": "none",
        "external_memory": "none"
    }
    backend = build_memory_backend(tmp_path, config)
    assert isinstance(backend, SQLiteMemoryBackend)
    assert backend.db_path == tmp_path / "data" / "vaila_memory.sqlite3"

def test_invalid_backend_raises_clear_value_error(tmp_path: Path) -> None:
    config = {
        "backend": "invalid_backend_name",
        "sqlite_path": "data/vaila_memory.sqlite3",
        "vector_backend": "none",
        "external_memory": "none"
    }
    with pytest.raises(ValueError) as exc_info:
        build_memory_backend(tmp_path, config)
    assert "Invalid backend" in str(exc_info.value)

def test_existing_api_works_with_jsonl_default(tmp_path: Path) -> None:
    # Setup VailaCore on tmp_path
    profiles_dir = tmp_path / "data"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    profiles_file = profiles_dir / "model_profiles.json"
    with profiles_file.open("w", encoding="utf-8") as f:
        f.write(json.dumps({"profiles": {}}))

    core = VailaCore(tmp_path)
    core.load_local_state()

    # Confirms JsonlMemoryBackend is built by default
    assert isinstance(core.memory_backend, JsonlMemoryBackend)
    
    # Check adapters
    assert core.memory_store == core.memory_backend.memory_store
    assert core.candidate_store == core.memory_backend.candidate_store

    # Test health endpoint using test client
    client = TestClient(app)
    
    # Temporarily override service's core project root/state or use the core in app
    from app.service import core as service_core
    old_backend = service_core.memory_backend
    old_config = service_core.memory_config
    old_store = service_core.memory_store
    old_cand = service_core.candidate_store
    
    service_core.memory_config = {
        "backend": "jsonl",
        "sqlite_path": "data/vaila_memory.sqlite3",
        "vector_backend": "none",
        "external_memory": "none"
    }
    service_core.memory_backend = build_memory_backend(tmp_path, service_core.memory_config)
    service_core.memory_store = service_core.memory_backend.memory_store
    service_core.candidate_store = service_core.memory_backend.candidate_store
    
    try:
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        state = data["state"]
        assert state["memory_backend"] == "jsonl"
        assert state["vector_backend"] == "none"
        assert state["external_memory"] == "none"
    finally:
        # Restore service core
        service_core.memory_backend = old_backend
        service_core.memory_config = old_config
        service_core.memory_store = old_store
        service_core.candidate_store = old_cand

def test_sqlite_adapter_compatibility(tmp_path: Path) -> None:
    # Set up sqlite backend
    db_path = tmp_path / "data" / "vaila_memory.sqlite3"
    backend = SQLiteMemoryBackend(db_path)
    backend.load()

    # Verify adapter CRUD on sqlite
    mem_adapter = MemoryStoreAdapter(backend)
    cand_adapter = CandidateStoreAdapter(backend)

    # Initially empty
    assert len(mem_adapter.records) == 0
    assert len(cand_adapter.list_candidates("pending")) == 0

    # Add candidates
    from app.memory.models import MemoryCandidate, MemoryRecord
    candidate = MemoryCandidate(
        id="candidate_123",
        question="What is the unit test?",
        answer="A test of a single unit.",
        tags=["unit"],
        persona_scope=["all"],
    )
    added = cand_adapter.add_many([candidate])
    assert len(added) == 1
    assert added[0].id == "candidate_123"

    # List candidates
    pending = cand_adapter.list_candidates("pending")
    assert len(pending) == 1
    assert pending[0].question == "What is the unit test?"

    # Get single candidate
    fetched = cand_adapter.get("candidate_123")
    assert fetched is not None
    assert fetched.question == "What is the unit test?"

    # Approve
    backend.approve_candidate("candidate_123")
    assert len(mem_adapter.records) == 1
    assert mem_adapter.records[0].question == "What is the unit test?"
    
    # Counts
    assert mem_adapter.category_counts() == {"general": 1}
    assert "recent" in mem_adapter.recency_counts()

    backend.close()
