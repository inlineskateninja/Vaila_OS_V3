from __future__ import annotations

import json
import sys
from pathlib import Path
import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.memory.jsonl_backend import JsonlMemoryBackend
from app.memory.models import MemoryRecord, MemoryCandidate


@pytest.fixture
def temp_memory_dirs(tmp_path: Path) -> tuple[Path, Path]:
    mem_root = tmp_path / "system_wide_memory"
    cand_root = tmp_path / "sandbox" / "memory_candidates"
    mem_root.mkdir(parents=True)
    cand_root.mkdir(parents=True)
    return mem_root, cand_root


def test_jsonl_backend_loads_and_counts(temp_memory_dirs: tuple[Path, Path]) -> None:
    mem_root, cand_root = temp_memory_dirs

    # Write mock Memory Record
    record = MemoryRecord(
        id="memory_1",
        question="What is the standard lens?",
        answer="Proto Jane is the standard OS lens.",
        tags=["lens", "os"],
        persona_scope=["proto_jane"],
        category="general",
    )
    category_file = mem_root / "general.jsonl"
    with category_file.open("w", encoding="utf-8") as f:
        f.write(json.dumps(record.to_dict()) + "\n")

    # Write mock Pending Candidate
    candidate = MemoryCandidate(
        id="candidate_1",
        question="How does memory extraction work?",
        answer="It scans conversation streams.",
        tags=["memory", "extraction"],
        persona_scope=["all"],
        status="pending",
    )
    pending_file = cand_root / "pending.jsonl"
    with pending_file.open("w", encoding="utf-8") as f:
        f.write(json.dumps(candidate.to_dict()) + "\n")

    # Initialize JsonlMemoryBackend
    backend = JsonlMemoryBackend(mem_root, cand_root)
    backend.load()

    summary = backend.state_summary()
    assert summary["memory_records"] == 1
    assert summary["pending_candidates"] == 1
    assert summary["approved_candidates"] == 0


def test_jsonl_backend_lists_candidates(temp_memory_dirs: tuple[Path, Path]) -> None:
    mem_root, cand_root = temp_memory_dirs
    backend = JsonlMemoryBackend(mem_root, cand_root)
    backend.load()

    candidate = MemoryCandidate(
        id="candidate_abc",
        question="Test Q",
        answer="Test A",
        tags=["test"],
        persona_scope=["all"],
    )

    # Test create_candidates
    added = backend.create_candidates([candidate])
    assert len(added) == 1
    assert added[0].id == "candidate_abc"

    # Test list_candidates
    pending = backend.list_candidates("pending")
    assert len(pending) == 1
    assert pending[0].id == "candidate_abc"

    # Test get_candidate
    fetched = backend.get_candidate("candidate_abc")
    assert fetched is not None
    assert fetched.question == "Test Q"


def test_jsonl_backend_searches_memory(temp_memory_dirs: tuple[Path, Path]) -> None:
    mem_root, cand_root = temp_memory_dirs
    backend = JsonlMemoryBackend(mem_root, cand_root)
    backend.load()

    record1 = MemoryRecord(
        id="memory_xyz",
        question="What is Codex?",
        answer="An advanced sandboxed AI workspace.",
        tags=["codex"],
        persona_scope=["all"],
        relevance_score=1.0,
    )
    backend.append_memory(record1)

    # Test search_memory
    results = backend.search_memory("Codex", persona="proto_jane", limit=5)
    assert len(results) == 1
    assert results[0].id == "memory_xyz"

    # Test search_memory_scored
    results_scored = backend.search_memory_scored("Codex", persona="proto_jane", limit=5)
    assert len(results_scored) == 1
    score, record = results_scored[0]
    assert score > 0.0
    assert record.id == "memory_xyz"


def test_jsonl_backend_approves_candidate(temp_memory_dirs: tuple[Path, Path]) -> None:
    mem_root, cand_root = temp_memory_dirs
    backend = JsonlMemoryBackend(mem_root, cand_root)
    backend.load()

    candidate = MemoryCandidate(
        id="candidate_approved_test",
        question="Should this be approved?",
        answer="Yes, absolutely.",
        tags=["approval"],
        persona_scope=["all"],
    )
    backend.create_candidates([candidate])

    # Approve the candidate
    approved, written_path = backend.approve_candidate("candidate_approved_test")
    assert approved.status == "approved"
    assert approved.reviewed_at != ""
    assert written_path.exists()

    # Verify JSONL file was updated and loaded
    assert len(backend.list_candidates("pending")) == 0
    assert len(backend.list_candidates("approved")) == 1

    backend.load()
    assert len(backend.memory_store.records) == 1
    assert backend.memory_store.records[0].question == "Should this be approved?"


def test_jsonl_backend_rejects_candidate(temp_memory_dirs: tuple[Path, Path]) -> None:
    mem_root, cand_root = temp_memory_dirs
    backend = JsonlMemoryBackend(mem_root, cand_root)
    backend.load()

    candidate = MemoryCandidate(
        id="candidate_rejected_test",
        question="Should this be rejected?",
        answer="Yes.",
        tags=["rejection"],
        persona_scope=["all"],
    )
    backend.create_candidates([candidate])

    # Reject the candidate
    rejected = backend.reject_candidate("candidate_rejected_test", note="Not needed fact.")
    assert rejected.status == "rejected"
    assert rejected.review_note == "Not needed fact."

    # Verify JSONL file was updated
    assert len(backend.list_candidates("pending")) == 0
    assert len(backend.list_candidates("rejected")) == 1


def test_legacy_memory_record_dict_loading() -> None:
    # A minimal dictionary representing old, legacy JSONL records
    legacy_data = {
        "id": "memory_legacy_abc",
        "question": "What is the old format?",
        "answer": "It had only basic keys.",
        "tags": ["legacy"],
    }
    
    # from_dict must safely load legacy records without throwing exception
    record = MemoryRecord.from_dict(legacy_data)
    assert record.id == "memory_legacy_abc"
    assert record.question == "What is the old format?"
    
    # New fields should receive safe defaults
    assert record.review_status == "approved"
    assert record.approved_at == ""
    assert record.sensitivity == "normal"
    assert record.memory_type == "fact"
    assert record.created_by == "vaila"
    assert record.recall_count == 0


def test_memory_record_new_fields_serialization_deserialization() -> None:
    record = MemoryRecord(
        id="memory_meta_123",
        question="What is the meaning of metadata?",
        answer="Data about data.",
        tags=["meta"],
        sensitivity="high",
        memory_type="concept",
        expires_at="2030-01-01",
        recall_count="5",  # String that must get coerced to integer
    )
    
    data_dict = record.to_dict()
    assert data_dict["sensitivity"] == "high"
    assert data_dict["memory_type"] == "concept"
    assert data_dict["expires_at"] == "2030-01-01"
    assert data_dict["recall_count"] == "5"
    
    loaded = MemoryRecord.from_dict(data_dict)
    assert loaded.sensitivity == "high"
    assert loaded.memory_type == "concept"
    assert loaded.expires_at == "2030-01-01"
    assert loaded.recall_count == 5  # Coerced to integer!


def test_candidate_approval_propagates_metadata(temp_memory_dirs: tuple[Path, Path]) -> None:
    mem_root, cand_root = temp_memory_dirs
    backend = JsonlMemoryBackend(mem_root, cand_root)
    backend.load()

    candidate = MemoryCandidate(
        id="candidate_prop_test",
        question="Should metadata carry over?",
        answer="Yes, completely.",
        tags=["metadata", "carryover"],
        sensitivity="restricted",
        memory_type="policy",
        source_event_id="event_xyz",
        proposed_by="maelith",
    )
    backend.create_candidates([candidate])

    approved, _ = backend.approve_candidate("candidate_prop_test")
    assert approved.status == "approved"

    backend.load()
    assert len(backend.memory_store.records) == 1
    record = backend.memory_store.records[0]
    
    # Check that candidate properties successfully carried over
    assert record.id == "memory_prop_test"
    assert record.review_status == "approved"
    assert record.approved_at != ""
    assert record.sensitivity == "restricted"
    assert record.memory_type == "policy"
    assert record.source_event_id == "event_xyz"
    assert record.created_by == "maelith"

