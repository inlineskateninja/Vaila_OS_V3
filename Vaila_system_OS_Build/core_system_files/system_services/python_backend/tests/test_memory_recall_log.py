from __future__ import annotations

import json
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.memory.recall_log import MemoryRecallLog, MemoryRecallEvent
from app.memory.models import MemoryRecord
from app.schemas import RoutePlan
from app.core import VailaCore
from app.service import app


def test_recall_log_writes_and_loads_jsonl(tmp_path: Path) -> None:
    log_file = tmp_path / "memory_recall.jsonl"
    log = MemoryRecallLog(log_file)
    log.load()
    assert log.count() == 0

    event1 = MemoryRecallEvent(
        id="",
        created_at="",
        request_id="req_123",
        persona="proto_jane",
        task_type="general_chat",
        query="Code snippet",
        memory_ids=["memory_x"],
        scores=[0.85],
    )
    log.append(event1)
    assert log.count() == 1
    assert log.events[0].request_id == "req_123"

    # Reload from disk
    new_log = MemoryRecallLog(log_file)
    new_log.load()
    assert new_log.count() == 1
    assert new_log.events[0].query == "Code snippet"
    assert new_log.events[0].memory_ids == ["memory_x"]


def test_retrieve_memory_creates_recall_events(tmp_path: Path) -> None:
    # Set up temp VailaCore directories
    profiles_dir = tmp_path / "data"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    profiles_file = profiles_dir / "model_profiles.json"
    with profiles_file.open("w", encoding="utf-8") as f:
        f.write(json.dumps({"profiles": {}}))

    core = VailaCore(tmp_path)
    core.load_local_state()
    
    # Assert recall log starts empty
    assert core.memory_recall_log.count() == 0

    route_plan = RoutePlan(
        user_text="What is Codex?",
        task_type="general_chat",
        persona="proto_jane",
        model_tier="medium",
        model_profile="default",
        fallback_profile="default",
        memory_queries=["Codex"],
        memory_tags=[],
        reasons=[],
    )
    
    # Retrieve memory (will trigger recall log write)
    core.retrieve_memory(route_plan, per_query_limit=3, request_id="req_test_abc")
    
    # Assert event was logged
    assert core.memory_recall_log.count() == 1
    event = core.memory_recall_log.events[0]
    assert event.request_id == "req_test_abc"
    assert event.persona == "proto_jane"
    assert event.query == "Codex"
    
    # Verify health/state summary includes recall count
    summary = core.state_summary()
    assert summary["memory_recall_events"] == 1


def test_api_endpoint_returns_recalls(tmp_path: Path) -> None:
    # Make sure we use a clean test client
    client = TestClient(app)
    
    # Let's populate some mock events in the global core in service
    from app.service import core as service_core
    service_core.memory_recall_log.file_path = tmp_path / "service_recall.jsonl"
    service_core.memory_recall_log.load()
    
    event = MemoryRecallEvent(
        id="recall_api_1",
        created_at="",
        request_id="req_api",
        persona="maelith",
        task_type="analysis",
        query="System design",
        memory_ids=["memory_y"],
        scores=[0.92],
    )
    service_core.memory_recall_log.append(event)
    
    # Request API GET
    response = client.get("/memory/recalls?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert len(data["events"]) == 1
    assert data["events"][0]["id"] == "recall_api_1"
    assert data["events"][0]["query"] == "System design"
    assert data["events"][0]["persona"] == "maelith"
