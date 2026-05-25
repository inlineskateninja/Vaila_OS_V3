from __future__ import annotations

import json
import sys
from pathlib import Path
import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.memory.sqlite_backend import SQLiteMemoryBackend
from app.memory.models import MemoryRecord, MemoryCandidate

@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    return tmp_path / "vaila_memory.sqlite3"

def test_sqlite_backend_loads_and_counts(temp_db_path: Path) -> None:
    backend = SQLiteMemoryBackend(temp_db_path)
    backend.load()

    # Verify counts are 0
    summary = backend.state_summary()
    assert summary["memory_records"] == 0
    assert summary["pending_candidates"] == 0
    assert summary["approved_candidates"] == 0
    assert summary["rejected_candidates"] == 0

    backend.close()

def test_sqlite_backend_candidates_crud(temp_db_path: Path) -> None:
    backend = SQLiteMemoryBackend(temp_db_path)
    backend.load()

    candidate = MemoryCandidate(
        id="candidate_1",
        question="How does SQLite work?",
        answer="It is a serverless, self-contained database.",
        tags=["sqlite", "database"],
        persona_scope=["proto_jane", "all"],
        category="technical",
        confidence="high",
        sensitivity="normal",
        memory_type="fact",
        proposed_by="maelith",
        requires_user_approval=True,
    )

    # Test create_candidates
    added = backend.create_candidates([candidate])
    assert len(added) == 1
    assert added[0].id == "candidate_1"

    # Test list_candidates
    pending = backend.list_candidates("pending")
    assert len(pending) == 1
    assert pending[0].id == "candidate_1"
    assert pending[0].question == "How does SQLite work?"
    assert pending[0].tags == ["sqlite", "database"]
    assert "proto_jane" in pending[0].persona_scope

    # Test get_candidate
    fetched = backend.get_candidate("candidate_1")
    assert fetched is not None
    assert fetched.question == "How does SQLite work?"

    backend.close()

def test_sqlite_backend_approves_candidate(temp_db_path: Path) -> None:
    backend = SQLiteMemoryBackend(temp_db_path)
    backend.load()

    candidate = MemoryCandidate(
        id="candidate_2",
        question="Should we approve SQLite?",
        answer="Yes, as an optional backend.",
        tags=["sqlite", "optional"],
        persona_scope=["all"],
        category="decision",
        confidence="high",
        sensitivity="restricted",
        memory_type="policy",
        proposed_by="vaila",
    )
    backend.create_candidates([candidate])

    # Approve
    approved, db_path = backend.approve_candidate("candidate_2")
    assert approved.status == "approved"
    assert approved.reviewed_at != ""
    assert db_path == temp_db_path

    # Verify candidate status updated
    assert len(backend.list_candidates("pending")) == 0
    assert len(backend.list_candidates("approved")) == 1

    # Verify memory item created
    summary = backend.state_summary()
    assert summary["memory_records"] == 1

    # Let's inspect the record via direct DB fetch or reload and search
    records = backend.search_memory("SQLite", persona="proto_jane")
    assert len(records) == 1
    record = records[0]
    assert record.id == "memory_2"
    assert record.question == "Should we approve SQLite?"
    assert record.sensitivity == "restricted"
    assert record.memory_type == "policy"
    assert record.created_by == "vaila"
    assert record.review_status == "approved"

    backend.close()

def test_sqlite_backend_reject_candidate(temp_db_path: Path) -> None:
    backend = SQLiteMemoryBackend(temp_db_path)
    backend.load()

    candidate = MemoryCandidate(
        id="candidate_3",
        question="Should we make SQLite the default?",
        answer="Not yet, preserve JSONL as default.",
        tags=["sqlite", "default"],
        persona_scope=["all"],
    )
    backend.create_candidates([candidate])

    # Reject
    rejected = backend.reject_candidate("candidate_3", note="Preserve JSONL for compatibility.")
    assert rejected.status == "rejected"
    assert rejected.review_note == "Preserve JSONL for compatibility."

    # Verify candidate status updated
    assert len(backend.list_candidates("pending")) == 0
    assert len(backend.list_candidates("rejected")) == 1

    # Verify no memory item created
    summary = backend.state_summary()
    assert summary["memory_records"] == 0

    backend.close()

def test_sqlite_backend_search_and_scoring(temp_db_path: Path) -> None:
    backend = SQLiteMemoryBackend(temp_db_path)
    backend.load()

    # Append record 1
    record1 = MemoryRecord(
        id="mem_a",
        question="What is Codex?",
        answer="Codex is a secure sandbox execution environment.",
        tags=["codex", "sandbox"],
        persona_scope=["proto_jane"],
        category="architecture",
        confidence="high",
        relevance_score=1.0,
    )
    backend.append_memory(record1)

    # Append record 2 (different persona)
    record2 = MemoryRecord(
        id="mem_b",
        question="What is the active lens?",
        answer="Vaila's active lens is proto_jane.",
        tags=["lens"],
        persona_scope=["proto_jane"],
        category="architecture",
        confidence="normal",
        relevance_score=0.8,
    )
    backend.append_memory(record2)

    # Search for Codex
    results = backend.search_memory("Codex", persona="proto_jane")
    assert len(results) >= 1
    assert results[0].id == "mem_a"

    # Search scored
    results_scored = backend.search_memory_scored("Codex sandbox", persona="proto_jane")
    assert len(results_scored) >= 1
    score, top_rec = results_scored[0]
    assert top_rec.id == "mem_a"
    assert score > 0.0

    backend.close()

def test_sqlite_backend_disk_reload(temp_db_path: Path) -> None:
    # 1. Initialize, insert record and candidate, and close
    backend1 = SQLiteMemoryBackend(temp_db_path)
    backend1.load()

    candidate = MemoryCandidate(
        id="cand_persist",
        question="Is it persistent?",
        answer="Yes, SQLite stores data on disk.",
        tags=["persistence"],
        persona_scope=["all"],
    )
    backend1.create_candidates([candidate])

    record = MemoryRecord(
        id="mem_persist",
        question="Where is the file?",
        answer="At data/vaila_memory.sqlite3.",
        tags=["filepath"],
        persona_scope=["all"],
    )
    backend1.append_memory(record)

    backend1.close()

    # 2. Re-initialize from the same disk path
    backend2 = SQLiteMemoryBackend(temp_db_path)
    backend2.load()

    summary = backend2.state_summary()
    assert summary["memory_records"] == 1
    assert summary["pending_candidates"] == 1

    fetched_cand = backend2.get_candidate("cand_persist")
    assert fetched_cand is not None
    assert fetched_cand.question == "Is it persistent?"

    results = backend2.search_memory("filepath", persona="proto_jane")
    assert len(results) == 1
    assert results[0].id == "mem_persist"

    backend2.close()
