from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.memory.models import MemoryRecord, MemoryCandidate
from app.memory.migrate import migrate_jsonl_to_sqlite
from app.memory.sqlite_backend import SQLiteMemoryBackend
from app.service import app

@pytest.fixture
def mock_jsonl_project(tmp_path: Path) -> tuple[Path, Path, Path]:
    project_root = tmp_path / "vaila_project"
    project_root.mkdir()
    
    # Create data/ directory structures
    data_dir = project_root / "data"
    data_dir.mkdir()
    
    mem_dir = data_dir / "memory"
    mem_dir.mkdir()
    
    cand_dir = data_dir / "memory_candidates"
    cand_dir.mkdir()

    # Define some memory records
    record1 = MemoryRecord(
        id="memory_rec1",
        question="What is the color of Vaila?",
        answer="Vaila OS has premium, vibrant colors.",
        tags=["aesthetic"],
        persona_scope=["all"],
        category="general",
    )
    record2 = MemoryRecord(
        id="memory_rec2",
        question="What is Antigravity?",
        answer="Antigravity is a powerful AI companion by Google DeepMind.",
        tags=["antigravity"],
        persona_scope=["proto_jane"],
        category="general",
    )
    
    # Write to JSONL
    with (mem_dir / "general.jsonl").open("w", encoding="utf-8") as f:
        f.write(json.dumps(record1.to_dict()) + "\n")
        f.write(json.dumps(record2.to_dict()) + "\n")

    # Define some candidates
    cand1 = MemoryCandidate(
        id="candidate_pending1",
        question="Is memory active?",
        answer="Yes, it uses configuration layer.",
        tags=["config"],
        persona_scope=["all"],
        status="pending",
    )
    cand2 = MemoryCandidate(
        id="candidate_approved1",
        question="Should we approve config selection?",
        answer="Yes, configuration selection is supported.",
        tags=["config", "approved"],
        persona_scope=["all"],
        status="approved",
        reviewed_at="2026-05-24T20:30:00Z",
    )
    cand3 = MemoryCandidate(
        id="candidate_rejected1",
        question="Should we delete all memory?",
        answer="No, keep all memory safe.",
        tags=["danger"],
        persona_scope=["all"],
        status="rejected",
        reviewed_at="2026-05-24T20:30:00Z",
        review_note="Destructive operations rejected.",
    )
    
    # Write candidates
    with (cand_dir / "pending.jsonl").open("w", encoding="utf-8") as f:
        f.write(json.dumps(cand1.to_dict()) + "\n")
    with (cand_dir / "reviewed.jsonl").open("w", encoding="utf-8") as f:
        f.write(json.dumps(cand2.to_dict()) + "\n")
        f.write(json.dumps(cand3.to_dict()) + "\n")
        
    sqlite_path = data_dir / "vaila_memory.sqlite3"
    
    return project_root, sqlite_path, data_dir

def test_migration_dry_run_writes_nothing(mock_jsonl_project: tuple[Path, Path, Path]) -> None:
    project_root, sqlite_path, data_dir = mock_jsonl_project
    
    # Dry run
    summary = migrate_jsonl_to_sqlite(project_root, sqlite_path=sqlite_path, dry_run=True)
    
    assert summary["dry_run"] is True
    assert summary["memory_records_found"] == 2
    assert summary["memory_records_inserted"] == 2
    assert summary["candidates_found"] == 3
    assert summary["candidates_inserted"] == 3
    assert summary["skipped_duplicates"] == 0
    assert len(summary["errors"]) == 0
    
    # SQLite file must not exist after dry run
    assert not sqlite_path.exists()

def test_migration_real_run_copies_records_preserves_status_and_untouches_jsonl(
    mock_jsonl_project: tuple[Path, Path, Path]
) -> None:
    project_root, sqlite_path, data_dir = mock_jsonl_project
    
    # Check original JSONL contents first
    jsonl_records_path = data_dir / "memory" / "general.jsonl"
    jsonl_pending_path = data_dir / "memory_candidates" / "pending.jsonl"
    
    original_records_content = jsonl_records_path.read_text("utf-8")
    original_pending_content = jsonl_pending_path.read_text("utf-8")
    
    # Real run
    summary = migrate_jsonl_to_sqlite(project_root, sqlite_path=sqlite_path, dry_run=False)
    
    assert summary["dry_run"] is False
    assert summary["memory_records_found"] == 2
    assert summary["memory_records_inserted"] == 2
    assert summary["candidates_found"] == 3
    assert summary["candidates_inserted"] == 3
    assert summary["skipped_duplicates"] == 0
    assert len(summary["errors"]) == 0
    
    # SQLite file must now exist
    assert sqlite_path.exists()
    
    # Verify values inside SQLite
    backend = SQLiteMemoryBackend(sqlite_path)
    backend.load()
    
    try:
        # Check records
        records = backend.search_memory("", persona="proto_jane")
        assert len(records) == 2
        record_ids = {r.id for r in records}
        assert "memory_rec1" in record_ids
        assert "memory_rec2" in record_ids
        
        # Check candidates status
        cands = backend.list_candidates("all")
        assert len(cands) == 3
        cand_map = {c.id: c for c in cands}
        
        assert cand_map["candidate_pending1"].status == "pending"
        
        assert cand_map["candidate_approved1"].status == "approved"
        assert cand_map["candidate_approved1"].reviewed_at == "2026-05-24T20:30:00Z"
        
        assert cand_map["candidate_rejected1"].status == "rejected"
        assert cand_map["candidate_rejected1"].reviewed_at == "2026-05-24T20:30:00Z"
        assert cand_map["candidate_rejected1"].review_note == "Destructive operations rejected."
    finally:
        backend.close()
        
    # Verify original JSONL files remain completely untouched
    assert jsonl_records_path.read_text("utf-8") == original_records_content
    assert jsonl_pending_path.read_text("utf-8") == original_pending_content

def test_migration_running_twice_avoids_duplicates(mock_jsonl_project: tuple[Path, Path, Path]) -> None:
    project_root, sqlite_path, data_dir = mock_jsonl_project
    
    # First real run
    summary1 = migrate_jsonl_to_sqlite(project_root, sqlite_path=sqlite_path, dry_run=False)
    assert summary1["memory_records_inserted"] == 2
    assert summary1["candidates_inserted"] == 3
    assert summary1["skipped_duplicates"] == 0
    
    # Second real run
    summary2 = migrate_jsonl_to_sqlite(project_root, sqlite_path=sqlite_path, dry_run=False)
    assert summary2["memory_records_inserted"] == 0
    assert summary2["candidates_inserted"] == 0
    assert summary2["skipped_duplicates"] == 5
    assert len(summary2["errors"]) == 0
    
    # Verify count inside SQLite is still correct
    backend = SQLiteMemoryBackend(sqlite_path)
    backend.load()
    try:
        assert len(backend.search_memory("", persona="proto_jane")) == 2
        assert len(backend.list_candidates("all")) == 3
    finally:
        backend.close()

def test_migration_api_endpoint(mock_jsonl_project: tuple[Path, Path, Path]) -> None:
    project_root, sqlite_path, data_dir = mock_jsonl_project
    client = TestClient(app)
    
    from app.service import core as service_core
    old_root = service_core.project_root
    
    # Override service core's project root dynamically to point to our mock setup
    service_core.project_root = project_root
    
    # Write a custom memory config in the mock project root's data directory so load_memory_config resolves mock sqlite_path
    config_data = {
        "backend": "jsonl",
        "sqlite_path": str(sqlite_path),
        "vector_backend": "none",
        "external_memory": "none"
    }
    with (data_dir / "memory_config.json").open("w", encoding="utf-8") as f:
        json.dump(config_data, f)
        
    try:
        # 1. API Dry Run POST
        response = client.post("/memory/migrate/jsonl-to-sqlite", json={"dry_run": True})
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        summary = data["summary"]
        assert summary["dry_run"] is True
        assert summary["memory_records_found"] == 2
        assert summary["memory_records_inserted"] == 2
        assert not sqlite_path.exists()
        
        # 2. API Real Run POST
        response = client.post("/memory/migrate/jsonl-to-sqlite", json={"dry_run": False})
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        summary = data["summary"]
        assert summary["dry_run"] is False
        assert summary["memory_records_inserted"] == 2
        assert sqlite_path.exists()
    finally:
        service_core.project_root = old_root
