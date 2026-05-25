from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.core import VailaCore
from app.routers.system_perception_router import router as system_perception_router
from app.memory import migrate_jsonl_to_sqlite



class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    include_context: bool = False
    response_type: str = Field(default="short_text", min_length=1)
    persona_id: str | None = None
    device_id: str | None = None
    device_type: str | None = None
    location_available: bool = False
    location_opt_in: bool = False


class ImportDocumentRequest(BaseModel):
    path: str = Field(..., min_length=1)
    tags: list[str] = Field(default_factory=list)
    persona_scope: list[str] = Field(default_factory=lambda: ["all"])


class AnalyzeFileRequest(BaseModel):
    path: str = Field(..., min_length=1)


class MemorySearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    persona: str = "proto_jane"
    tags: list[str] = Field(default_factory=list)
    limit: int = Field(default=8, ge=1, le=50)
    category: str | None = None


class RejectCandidateRequest(BaseModel):
    note: str = ""


class DeleteMemoryProposalRequest(BaseModel):
    topic: str = Field(..., min_length=1)
    limit: int = Field(default=20, ge=1, le=100)


class MigrationRequest(BaseModel):
    dry_run: bool = True


core = VailaCore()


@asynccontextmanager
async def lifespan(app: FastAPI):
    core.load_local_state()
    app.state.model_status = core.resolve_models()
    yield


app = FastAPI(
    title="Vaila Persona Core API",
    description="Local Phase 2 API for chat, memory search, document import, persona library, model evaluation, and memory candidate review.",
    version="0.2.4",
    lifespan=lifespan,
)
app.include_router(system_perception_router)


def _raise_as_http(error: Exception) -> None:
    if isinstance(error, FileNotFoundError):
        raise HTTPException(status_code=404, detail=str(error)) from error
    if isinstance(error, KeyError):
        raise HTTPException(status_code=404, detail=str(error)) from error
    if isinstance(error, ValueError):
        raise HTTPException(status_code=400, detail=str(error)) from error
    raise HTTPException(status_code=500, detail=str(error)) from error


@app.get("/")
def root() -> dict[str, Any]:
    return {"name": "Vaila Persona Core API", "version": "0.2.4", "docs": "/docs", "health": "/health"}


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "state": core.state_summary(), "model_status": core.last_model_resolution}


@app.post("/reload")
def reload_state() -> dict[str, Any]:
    return {"ok": True, "state": core.reload()}


@app.get("/commands")
def commands() -> dict[str, Any]:
    return {"ok": True, "commands": core.memory_commands()}


@app.get("/response-types")
def response_types() -> dict[str, Any]:
    return {"ok": True, "response_types": core.response_type_options()}


@app.get("/tools")
def tools() -> dict[str, Any]:
    return {"ok": True, "tools": core.tool_registry()}


@app.get("/integrations")
def integrations() -> dict[str, Any]:
    return {"ok": True, "integrations": core.service_registry()}


@app.get("/integrations/{name}/health")
def integration_health(name: str) -> dict[str, Any]:
    return core.service_health(name)


@app.get("/context-tools")
def context_tools() -> dict[str, Any]:
    return {"ok": True, "context_tools": core.context_tool_registry()}


@app.get("/tools/recent")
def recent_tool_result(tool_name: str | None = None) -> dict[str, Any]:
    record = core.recent_tool_result(tool_name)
    return {"ok": True, "tool_result": record}


@app.get("/personas")
def personas() -> dict[str, Any]:
    return {"ok": True, "personas": core.list_personas()}


@app.post("/models/resolve")
def resolve_models() -> dict[str, Any]:
    return core.resolve_models()


@app.get("/models")
def list_models() -> dict[str, Any]:
    return {"ok": True, "model_status": core.last_model_resolution, "profiles": core._model_profiles_as_dict()}


@app.get("/models/evaluation")
def model_evaluation() -> dict[str, Any]:
    return core.model_evaluation()


@app.post("/chat")
def chat(request: ChatRequest) -> dict[str, Any]:
    try:
        return core.chat(
            request.message,
            include_context=request.include_context,
            response_type=request.response_type,
            persona_id=request.persona_id,
            device_id=request.device_id,
            device_type=request.device_type,
            location_available=request.location_available,
            location_opt_in=request.location_opt_in,
        )
    except Exception as error:
        _raise_as_http(error)


@app.post("/documents/import")
def import_document(request: ImportDocumentRequest) -> dict[str, Any]:
    try:
        return core.import_document(path=request.path, tags=request.tags, persona_scope=request.persona_scope)
    except Exception as error:
        _raise_as_http(error)


@app.post("/files/analyze")
def analyze_file(request: AnalyzeFileRequest) -> dict[str, Any]:
    try:
        return core.analyze_file(path=request.path)
    except Exception as error:
        _raise_as_http(error)


@app.get("/candidates")
def list_candidates(status: str = "pending") -> dict[str, Any]:
    if status not in {"pending", "all", "approved", "rejected"}:
        raise HTTPException(status_code=400, detail="status must be pending, all, approved, or rejected")
    return {"ok": True, "status": status, "candidates": core.list_candidates(status)}


@app.get("/candidates/{candidate_id}")
def get_candidate(candidate_id: str) -> dict[str, Any]:
    candidate = core.get_candidate(candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail=f"Unknown candidate: {candidate_id}")
    return {"ok": True, "candidate": candidate.to_dict()}


@app.post("/candidates/{candidate_id}/approve")
def approve_candidate(candidate_id: str) -> dict[str, Any]:
    try:
        return core.approve_candidate(candidate_id)
    except Exception as error:
        _raise_as_http(error)


@app.post("/candidates/{candidate_id}/reject")
def reject_candidate(candidate_id: str, request: RejectCandidateRequest | None = None) -> dict[str, Any]:
    try:
        note = request.note if request else ""
        return core.reject_candidate(candidate_id, note=note)
    except Exception as error:
        _raise_as_http(error)


@app.post("/memory/search")
def search_memory(request: MemorySearchRequest) -> dict[str, Any]:
    return {"ok": True, "records": core.search_memory(query=request.query, persona=request.persona, tags=request.tags, limit=request.limit, category=request.category)}


@app.post("/memory/propose-from-chat")
def propose_from_chat(limit: int = 20) -> dict[str, Any]:
    return core.propose_memories_from_recent_chat(limit=limit)


@app.post("/memory/delete-proposal")
def delete_memory_proposal(request: DeleteMemoryProposalRequest) -> dict[str, Any]:
    return core.delete_memory_proposal(topic=request.topic, limit=request.limit)


@app.get("/activity")
def recent_activity(limit: int = 50, event_type: str | None = None) -> dict[str, Any]:
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 200")
    return {"ok": True, "events": core.recent_activity(limit=limit, event_type=event_type)}


@app.get("/project/review")
def project_review(limit: int = 50) -> dict[str, Any]:
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 200")
    return core.project_review(limit=limit)


@app.get("/memory/recalls")
def recent_memory_recalls(limit: int = 50) -> dict[str, Any]:
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 200")
    events = core.memory_recall_log.list_recent(limit=limit)
    return {"ok": True, "limit": limit, "events": [event.to_dict() for event in events]}


@app.post("/memory/migrate/jsonl-to-sqlite")
def migrate_memory(request: MigrationRequest) -> dict[str, Any]:
    summary = migrate_jsonl_to_sqlite(core.project_root, dry_run=request.dry_run)
    return {"ok": len(summary["errors"]) == 0, "summary": summary}
