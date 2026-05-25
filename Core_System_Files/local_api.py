from __future__ import annotations

import json
import sys
import os
import shutil
import time
import hmac
from pathlib import Path
from typing import Any
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from fastapi import FastAPI, Response, UploadFile, File, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from System_Services.envelope_service import EnvelopeService
from System_Services.logging_service import LoggingService
from System_Services.orchestration_service import OrchestrationService
from System_Services.router_service import RouterService
from System_Services.connected_service_manager import ConnectedServiceManager

app = FastAPI(title="Vaila OS V3 Local API & GUI", version="0.3.0")


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name: str) -> list[str]:
    value = os.getenv(name, "")
    return [item.strip() for item in value.split(",") if item.strip()]


REMOTE_ACCESS_ENABLED = _env_bool("VAILA_REMOTE_ACCESS_ENABLED")
WEB_AUTH_TOKEN = os.getenv("VAILA_WEB_AUTH_TOKEN", "").strip()
AUTH_REQUIRED = REMOTE_ACCESS_ENABLED or bool(WEB_AUTH_TOKEN)
ALLOWED_CORS_ORIGINS = _env_list("VAILA_ALLOWED_ORIGINS")
PUBLIC_PATH_PREFIXES = ("/static/",)
PUBLIC_PATHS = {"/", "/api/auth/status"}

# Same-origin web access does not need CORS. Add explicit origins in .env only
# when a separate trusted client origin must call this API from a browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _extract_bearer_token(request: Request) -> str:
    auth_header = request.headers.get("authorization", "")
    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() == "bearer":
        return token.strip()
    return request.headers.get("x-vaila-token", "").strip()


@app.middleware("http")
async def require_remote_auth(request: Request, call_next):
    if not AUTH_REQUIRED:
        return await call_next(request)

    path = request.url.path
    if path in PUBLIC_PATHS or any(path.startswith(prefix) for prefix in PUBLIC_PATH_PREFIXES):
        return await call_next(request)

    if not WEB_AUTH_TOKEN:
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Remote access is enabled but VAILA_WEB_AUTH_TOKEN is not configured."
            },
        )

    supplied_token = _extract_bearer_token(request)
    if not hmac.compare_digest(supplied_token, WEB_AUTH_TOKEN):
        return JSONResponse(status_code=401, content={"detail": "Authentication required."})

    return await call_next(request)

logger = LoggingService(project_root=PROJECT_ROOT)
envelope_service = EnvelopeService(project_root=PROJECT_ROOT)
router = RouterService(project_root=PROJECT_ROOT)
orchestrator = OrchestrationService(project_root=PROJECT_ROOT, logger=logger)
service_manager = ConnectedServiceManager(project_root=PROJECT_ROOT)

# Thread Pool for executing parallel Council requests
thread_executor = ThreadPoolExecutor(max_workers=5)

# Models
class ChatRequest(BaseModel):
    text: str
    persona: str | None = None
    source: str = "local_api"
    session_id: str | None = None

class ClearRequest(BaseModel):
    session_id: str | None = None

class CouncilRequest(BaseModel):
    prompt: str
    personas: list[str]

class CouncilSynthesisRequest(BaseModel):
    responses: dict[str, str]

class UpdateCandidateRequest(BaseModel):
    status: str
    text: str | None = None

class DurableMemoryRequest(BaseModel):
    text: str
    category: str
    project_only: bool
    original_candidate: str | None = None

class AnalyzeFileRequest(BaseModel):
    filename: str

class ImportLocalProfileRequest(BaseModel):
    zip_path: str

class SaveModuleRequest(BaseModel):
    content: str

class SimulateRouteRequest(BaseModel):
    prompt: str

# Helper Functions
def read_recent_logs(folder_name: str, prefix: str, limit: int = 50) -> list[dict[str, Any]]:
    folder = PROJECT_ROOT / "System_Logging" / folder_name
    if not folder.exists():
        return []
    files = sorted(folder.glob(f"{prefix}_*.jsonl"), reverse=True)
    if not files:
        return []

    events: list[dict[str, Any]] = []
    for file_path in files[:3]:  # Read recent 3 daily files max
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.read().splitlines()
            for line in reversed(lines):
                if not line.strip():
                    continue
                try:
                    events.append(json.loads(line))
                except Exception:
                    events.append({"raw": line})
                if len(events) >= limit:
                    break
        except Exception:
            continue
        if len(events) >= limit:
            break
    return events

def load_memory_candidates() -> list[dict[str, Any]]:
    candidates_file = PROJECT_ROOT / "data" / "openbrain_memory_candidates.jsonl"
    if not candidates_file.exists():
        return []
    
    candidates = []
    try:
        lines = candidates_file.read_text(encoding="utf-8").splitlines()
        for line in lines:
            if not line.strip():
                continue
            try:
                item = json.loads(line)
                if isinstance(item, dict):
                    candidates.append(item)
            except json.JSONDecodeError:
                continue
    except Exception as exc:
        logger.log_error({"event_type": "api_load_candidates_failed", "error": str(exc)})
    return candidates

def load_durable_memories() -> list[dict[str, Any]]:
    durable_file = PROJECT_ROOT / "data" / "openbrain_durable_memories.jsonl"
    if not durable_file.exists():
        return []
    
    memories = []
    try:
        lines = durable_file.read_text(encoding="utf-8").splitlines()
        for line in lines:
            if not line.strip():
                continue
            try:
                item = json.loads(line)
                if isinstance(item, dict):
                    memories.append(item)
            except json.JSONDecodeError:
                continue
    except Exception as exc:
        logger.log_error({"event_type": "api_load_durable_failed", "error": str(exc)})
    return memories

# --- ROUTING ENDPOINTS ---

def _static_text(filename: str) -> str | None:
    static_file = PROJECT_ROOT / "Core_System_Files" / "static" / filename
    if static_file.exists():
        return static_file.read_text(encoding="utf-8")
    return None


def _is_mobile_request(request: Request) -> bool:
    user_agent = request.headers.get("user-agent", "").lower()
    mobile_markers = ("android", "iphone", "ipad", "ipod", "mobile")
    return any(marker in user_agent for marker in mobile_markers)


def _serve_gui_asset(filename: str) -> HTMLResponse:
    content = _static_text(filename)
    if content is not None:
        return HTMLResponse(content=content)
    return HTMLResponse(
        content="""
        <html>
            <body style="background:#090d16; color:#e2e8f0; font-family:sans-serif; text-align:center; padding-top:100px;">
                <h1>Vaila OS Web GUI assets not found.</h1>
                <p>Ensure the files are placed under <code>Core_System_Files/static/</code></p>
            </body>
        </html>
        """
    )


# HTML GUI Serving
@app.get("/")
def serve_index(request: Request) -> HTMLResponse:
    if _is_mobile_request(request):
        return _serve_gui_asset("mobile.html")
    return _serve_gui_asset("index.html")


@app.get("/mobile")
def serve_mobile_index() -> HTMLResponse:
    return _serve_gui_asset("mobile.html")


@app.get("/desktop")
def serve_desktop_index() -> HTMLResponse:
    return _serve_gui_asset("index.html")


@app.get("/static/style.css")
def serve_style() -> Response:
    content = _static_text("style.css")
    if content is not None:
        return Response(content=content, media_type="text/css")
    return Response(status_code=404)

@app.get("/static/app.js")
def serve_js() -> Response:
    content = _static_text("app.js")
    if content is not None:
        return Response(content=content, media_type="application/javascript")
    return Response(status_code=404)


@app.get("/static/mobile.css")
def serve_mobile_style() -> Response:
    content = _static_text("mobile.css")
    if content is not None:
        return Response(content=content, media_type="text/css")
    return Response(status_code=404)


@app.get("/static/mobile.js")
def serve_mobile_js() -> Response:
    content = _static_text("mobile.js")
    if content is not None:
        return Response(content=content, media_type="application/javascript")
    return Response(status_code=404)

@app.get("/api/auth/status")
def auth_status() -> dict[str, Any]:
    return {
        "auth_required": AUTH_REQUIRED,
        "remote_access_enabled": REMOTE_ACCESS_ENABLED,
        "cors_origins_configured": bool(ALLOWED_CORS_ORIGINS),
    }

@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "project_root": str(PROJECT_ROOT),
    }

@app.get("/api/personas")
def get_personas() -> list[dict[str, Any]]:
    return [
        {
            "id": "proto_jane",
            "name": "Proto Jane",
            "color": "cyan",
            "tagline": "Default Operating System lens",
            "description": "Technical, precise, balanced, and direct. Focused on clear operational alignment.",
        },
        {
            "id": "serren",
            "name": "Serren",
            "color": "emerald",
            "tagline": "Creative and cognitive lens",
            "description": "Exploratory, expansive, highly empathetic, and expressive. Explores implications and metaphors.",
        },
        {
            "id": "maelith",
            "name": "Maelith",
            "color": "ruby",
            "tagline": "Critical analysis lens",
            "description": "Deep analytical rigor, structural review, conflict checking, and optimization. Cuts through clutter.",
        },
        {
            "id": "vecht",
            "name": "Vecht",
            "color": "gold",
            "tagline": "Practical execution lens",
            "description": "Focused entirely on immediate actions, task lists, scheduling, and physical device constraints.",
        },
        {
            "id": "riven",
            "name": "Riven",
            "color": "violet",
            "tagline": "Self-assessment and growth lens",
            "description": "Reflects on the system's performance, code quality, architectural principles, and log history.",
        },
    ]

@app.get("/api/diagnostics")
def get_diagnostics() -> dict[str, Any]:
    return orchestrator.llm.diagnostics()

@app.get("/api/system_info")
def get_system_info() -> dict[str, Any]:
    return {
        "project_root": str(PROJECT_ROOT),
        "routing": "Deterministic Regex Router",
        "gateway": {
            "base_url": orchestrator.llm.base_url,
            "configured_model": orchestrator.llm.model,
            "resolved_model": orchestrator.llm._resolved_model or "(auto)",
        },
    }

@app.get("/api/logs/session")
def get_session_logs(limit: int = 50) -> list[dict[str, Any]]:
    return read_recent_logs("Session_Logs", "session", limit)

@app.get("/api/logs/errors")
def get_error_logs(limit: int = 50) -> list[dict[str, Any]]:
    return read_recent_logs("Error_Logs", "error", limit)

@app.post("/api/reports/summarize")
def run_summarize() -> dict[str, Any]:
    summary = orchestrator.log_summarizer.summarize_recent_logs()
    # Save as artifact
    art_dir = PROJECT_ROOT / "data" / "artifacts"
    art_dir.mkdir(parents=True, exist_ok=True)
    filename = f"log_summary_{time.strftime('%Y%m%d_%H%M%S')}.md"
    (art_dir / filename).write_text(f"# Log Summary Report\n\n{summary}", encoding="utf-8")
    
    logger.log_session_event({
        "event_type": "artifact_created",
        "artifact_type": "summaries",
        "filename": filename,
        "path": str(art_dir / filename)
    })
    return {"summary": summary, "filename": filename}

@app.post("/api/reports/self_assessment")
def run_self_assessment() -> dict[str, Any]:
    report = orchestrator.self_assessment.run_self_assessment()
    # Save as artifact
    art_dir = PROJECT_ROOT / "data" / "artifacts"
    art_dir.mkdir(parents=True, exist_ok=True)
    filename = f"self_assessment_{time.strftime('%Y%m%d_%H%M%S')}.md"
    (art_dir / filename).write_text(f"# Self Assessment Report\n\n{report}", encoding="utf-8")
    
    logger.log_session_event({
        "event_type": "artifact_created",
        "artifact_type": "system_scans",
        "filename": filename,
        "path": str(art_dir / filename)
    })
    return {"report": report, "filename": filename}

@app.post("/chat")
def chat(request: ChatRequest) -> dict[str, Any]:
    text = request.text
    if request.persona:
        text = f"{request.persona}, {text}"

    metadata = {
        "interface": "web_client",
        "selected_persona": request.persona or "proto_jane",
        "session_id": request.session_id or "web_session",
        "request_id": f"web_{uuid4().hex}"
    }
    envelope = envelope_service.create(user_text=text, source=request.source, metadata=metadata)
    route = router.route(envelope)
    response = orchestrator.handle(envelope=envelope, route=route)

    logger.log_session_event(
        {
            "event_type": "api_interaction_complete",
            "envelope": envelope.to_dict(),
            "route": route,
            "response_meta": response.meta,
        }
    )

    return {
        "text": response.visible_text,
        "route": route,
        "meta": response.meta,
    }

@app.post("/chat/clear")
def clear_chat_session(request: ClearRequest) -> dict[str, Any]:
    session_id = request.session_id or "web_session"
    orchestrator.clear_history(session_id)
    logger.log_session_event(
        {
            "event_type": "session_history_cleared",
            "session_id": session_id,
        }
    )
    return {"status": "success", "session_id": session_id}


# --- COUNCIL MODE ENDPOINTS ---

def execute_council_thread(prompt: str, p_id: str) -> dict[str, Any]:
    start_time = time.time()
    try:
        envelope = envelope_service.create(
            user_text=prompt,
            source="council_mode",
            metadata={"interface": "council_mode", "selected_persona": p_id}
        )
        route = {
            "task_type": "general_chat",
            "persona": p_id,
            "confidence": 1.0,
            "needs_prompt_interpreter": False
        }
        res = orchestrator.handle(envelope=envelope, route=route)
        elapsed = time.time() - start_time
        return {
            "persona": p_id,
            "text": res.visible_text,
            "elapsed": elapsed,
            "status": "completed"
        }
    except Exception as exc:
        return {
            "persona": p_id,
            "text": f"Dialog execution failed: {exc}",
            "elapsed": time.time() - start_time,
            "status": "failed"
        }

@app.post("/api/council")
def run_council(request: CouncilRequest) -> dict[str, Any]:
    prompt = request.prompt
    selected_personas = request.personas

    logger.log_session_event({
        "event_type": "council_assembly_started",
        "prompt": prompt,
        "personas": selected_personas
    })

    futures = []
    for p_id in selected_personas:
        f = thread_executor.submit(execute_council_thread, prompt, p_id)
        futures.append(f)

    results = {}
    statuses = {}
    for f in futures:
        r = f.result()
        p = r["persona"]
        results[p] = r["text"]
        statuses[p] = f"Completed in {r['elapsed']:.2f}s" if r["status"] == "completed" else "Failed"

    return {"results": results, "status": statuses}

@app.post("/api/council/synthesize")
def synthesize_council(request: CouncilSynthesisRequest) -> dict[str, Any]:
    responses = request.responses
    synth_prompt = "You are the Council Synthesizer. Malik asked a question and received answers from multiple personas. Please synthesize a unified, objective consensus report:\n\n"
    for name, resp in responses.items():
        synth_prompt += f"### PERSONA: {name.upper()}\n{resp}\n\n"
    
    synth_prompt += "### CONSENSUS SYNTHESIS:\n"

    envelope = envelope_service.create(
        user_text=synth_prompt,
        source="council_synthesis",
        metadata={"interface": "council_synthesis"}
    )
    route = {"task_type": "general_chat", "persona": "proto_jane", "confidence": 1.0}
    res = orchestrator.handle(envelope=envelope, route=route)

    # Save as artifact
    art_dir = PROJECT_ROOT / "data" / "artifacts"
    filename = f"council_synthesis_{time.strftime('%Y%m%d_%H%M%S')}.md"
    (art_dir / filename).write_text(res.visible_text, encoding="utf-8")

    logger.log_session_event({
        "event_type": "artifact_created",
        "artifact_type": "persona_comparisons",
        "filename": filename,
        "path": str(art_dir / filename)
    })

    return {"synthesis": res.visible_text, "filename": filename}

@app.post("/api/council/drift")
def calculate_council_drift(request: CouncilSynthesisRequest) -> dict[str, Any]:
    responses = request.responses
    drift_metrics = {}

    for name, resp in responses.items():
        words = resp.split()
        unique = set(w.lower() for w in words)
        density = len(unique) / len(words) if words else 0
        has_vaila = "vaila" in resp.lower() or "os" in resp.lower()
        drift_level = "STABLE" if density > 0.45 else "SLIGHT DRIFT"

        drift_metrics[name] = {
            "words_count": len(words),
            "density": f"{density:.2%}",
            "alignment": "MATCHED" if has_vaila else "STANDARDIZED",
            "drift_index": drift_level
        }

    return {"drift": drift_metrics}


# --- MEMORY CENTER ENDPOINTS ---

@app.get("/api/memory/candidates")
def get_memory_candidates() -> list[dict[str, Any]]:
    cands = load_memory_candidates()
    # Filter reviewable candidates
    return [c for c in cands if c.get("status") in {"needs_user_review", "candidate_logged"}]

@app.post("/api/memory/candidates/{cand_id}")
def update_memory_candidate(cand_id: str, request: UpdateCandidateRequest) -> dict[str, Any]:
    candidates_file = PROJECT_ROOT / "data" / "openbrain_memory_candidates.jsonl"
    if not candidates_file.exists():
        raise HTTPException(status_code=404, detail="Memory candidates queue not found.")

    updated_records = []
    found = False
    try:
        lines = candidates_file.read_text(encoding="utf-8").splitlines()
        for line in lines:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                if record.get("candidate_id") == cand_id:
                    record["status"] = request.status
                    if request.text is not None:
                        record["payload"]["text"] = request.text
                    found = True
                updated_records.append(record)
            except json.JSONDecodeError:
                continue

        with candidates_file.open("w", encoding="utf-8") as f:
            for r in updated_records:
                f.write(json.dumps(r) + "\n")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    if not found:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    return {"status": "success"}

@app.post("/api/memory/durable")
def add_durable_memory(request: DurableMemoryRequest) -> dict[str, Any]:
    durable_file = PROJECT_ROOT / "data" / "openbrain_durable_memories.jsonl"
    durable_file.parent.mkdir(parents=True, exist_ok=True)
    
    record = {
        "memory_id": f"dur_{uuid4().hex}",
        "approved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "text": request.text,
        "category": request.category,
        "project_only": request.project_only,
        "original_candidate": request.original_candidate
    }

    try:
        with durable_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    logger.log_session_event({
        "event_type": "memory_durable_created",
        "memory_id": record["memory_id"],
        "text": record["text"]
    })
    return {"status": "success", "memory": record}

@app.get("/api/memory/durable")
def get_durable_memories() -> list[dict[str, Any]]:
    return load_durable_memories()


# --- FILES WORKSPACE ENDPOINTS ---

@app.get("/api/files")
def get_imported_files() -> list[dict[str, Any]]:
    imp_dir = PROJECT_ROOT / "Sandbox" / "Imported_Documents"
    if not imp_dir.exists():
        return []
    
    files = []
    for p in sorted(imp_dir.glob("*"), key=os.path.getmtime, reverse=True):
        if p.is_file():
            files.append({
                "name": p.name,
                "size_kb": f"{p.stat().st_size / 1024:.1f} KB",
                "mtime": time.strftime("%H:%M:%S", time.localtime(p.stat().st_mtime)),
                "path": str(p)
            })
    return files

@app.post("/api/files/upload")
async def upload_workspace_file(file: UploadFile = File(...)) -> dict[str, Any]:
    dest_dir = PROJECT_ROOT / "Sandbox" / "Imported_Documents"
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    stamp = time.strftime("%Y%m%d_%H%M%S")
    dest_path = dest_dir / f"{stamp}_{file.filename}"
    
    try:
        with dest_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to copy file: {exc}")

    logger.log_session_event({
        "event_type": "workspace_file_imported",
        "filename": dest_path.name,
        "path": str(dest_path)
    })
    return {"status": "success", "filename": dest_path.name}

@app.post("/api/files/analyze")
def analyze_workspace_file(request: AnalyzeFileRequest) -> dict[str, Any]:
    file_path = PROJECT_ROOT / "Sandbox" / "Imported_Documents" / request.filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Imported file not found.")

    try:
        analysis = orchestrator.file_analyzer.analyze_file(str(file_path))
        # Save as scan report artifact
        art_dir = PROJECT_ROOT / "data" / "artifacts"
        filename = f"scan_{request.filename}.md"
        (art_dir / filename).write_text(analysis, encoding="utf-8")
        
        logger.log_session_event({
            "event_type": "artifact_created",
            "artifact_type": "system_scans",
            "filename": filename,
            "path": str(art_dir / filename)
        })
        return {"analysis": analysis, "filename": filename}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.post("/api/files/extract")
def extract_file_memories(request: AnalyzeFileRequest) -> dict[str, Any]:
    file_path = PROJECT_ROOT / "Sandbox" / "Imported_Documents" / request.filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Imported file not found.")

    drafted_count = 0
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
        for line in lines:
            line_clean = line.strip()
            if len(line_clean) < 15:
                continue

            should_extract = any(
                k in line_clean.lower()
                for k in ["prefer", "always", "never", "remember", "must", "should", "like", "favorite"]
            )

            if should_extract:
                cand = {
                    "event_type": "memory_candidate_detected",
                    "request_id": f"file_import_{time.strftime('%M%S')}",
                    "source": f"workspace_vault:{request.filename}",
                    "text": line_clean,
                    "route": {"task_type": "file_import"},
                    "status": "needs_user_review"
                }

                candidates_file = PROJECT_ROOT / "data" / "openbrain_memory_candidates.jsonl"
                candidates_file.parent.mkdir(parents=True, exist_ok=True)
                with candidates_file.open("a", encoding="utf-8") as f:
                    record = {
                        "candidate_id": f"ob_{uuid4().hex}",
                        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "service_id": "openbrain",
                        "mode": "local",
                        "status": "candidate_logged",
                        "payload": cand
                    }
                    f.write(json.dumps(record) + "\n")
                drafted_count += 1
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    logger.log_session_event({
        "event_type": "workspace_file_memory_extraction",
        "filename": request.filename,
        "candidates_count": drafted_count
    })
    return {"status": "success", "extracted_count": drafted_count}


# --- SYSTEM PERCEPTION MAP ENDPOINTS ---

@app.get("/api/system/map")
def get_system_map() -> dict[str, Any]:
    file_count = 0
    total_size = 0
    directory_lines = []

    expected_files = {
        ".env": PROJECT_ROOT / ".env",
        "requirements.txt": PROJECT_ROOT / "requirements.txt",
        "Core_System_Files/desktop_client.py": PROJECT_ROOT / "Core_System_Files" / "desktop_client.py",
        "System_Services/openbrain_service.py": PROJECT_ROOT / "System_Services" / "openbrain_service.py",
        "Persona_Files/Proto_Jane/identity.md": PROJECT_ROOT / "Persona_Files" / "Proto_Jane" / "identity.md",
        "Persona_Files/Vecht/identity.md": PROJECT_ROOT / "Persona_Files" / "Vecht" / "identity.md",
    }

    alerts = {}
    for name, path in expected_files.items():
        alerts[name] = path.exists()

    try:
        # Walk parent structure
        for p in PROJECT_ROOT.glob("*"):
            if p.name.startswith(".") or p.name == "__pycache__":
                continue
            if p.is_dir():
                directory_lines.append(f" 📂 {p.name}/")
                children = list(p.glob("*"))
                for c in children[:4]:
                    if c.name.startswith(".") or c.name == "__pycache__":
                        continue
                    suffix = "/" if c.is_dir() else ""
                    directory_lines.append(f"    📄 {c.name}{suffix}")
                if len(children) > 4:
                    directory_lines.append(f"    ... and {len(children)-4} more files")
            else:
                directory_lines.append(f" 📄 {p.name} ({p.stat().st_size/1024:.1f} KB)")

        # Recursive totals
        for p in PROJECT_ROOT.rglob("*"):
            if p.is_file() and not p.name.startswith(".") and "__pycache__" not in str(p):
                file_count += 1
                total_size += p.stat().st_size
    except Exception as exc:
        directory_lines.append(f"[SCAN FAILURE] {exc}")

    return {
        "file_count": file_count,
        "total_size_mb": f"{total_size / (1024*1024):.2f} MB",
        "alerts": alerts,
        "tree": directory_lines
    }

@app.get("/api/system/health")
def get_system_health() -> dict[str, Any]:
    # Check LM Studio
    diagnostics = orchestrator.llm.diagnostics()
    lm_studio = diagnostics.get("server_reachable", False)

    # Check OpenBrain Mode
    ob = orchestrator.memory.openbrain.is_configured()

    # Check TTS
    tts = False
    try:
        import pyttsx3
        tts = True
    except ImportError:
        pass

    # Check registered services status
    registries = service_manager.service_statuses()
    services_status = {}
    for name, data in registries.items():
        services_status[name] = data.get("enabled", False)

    return {
        "lm_studio": lm_studio,
        "lm_studio_endpoint": orchestrator.llm.base_url,
        "memory_db": ob,
        "memory_db_mode": orchestrator.memory.openbrain.mode,
        "tts": tts,
        "registries": services_status
    }

# --- ARTIFACTS LIST ENDPOINT ---

@app.get("/api/artifacts")
def get_artifacts() -> list[dict[str, Any]]:
    art_dir = PROJECT_ROOT / "data" / "artifacts"
    if not art_dir.exists():
        return []
    
    artifacts = []
    for p in sorted(art_dir.glob("*.md"), key=os.path.getmtime, reverse=True):
        artifacts.append({
            "name": p.name,
            "path": str(p),
            "size_kb": f"{p.stat().st_size / 1024:.1f} KB",
            "mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(p.stat().st_mtime))
        })
    return artifacts

@app.get("/api/artifacts/{filename}")
def get_artifact_content(filename: str) -> Response:
    art_file = PROJECT_ROOT / "data" / "artifacts" / filename
    if not art_file.exists():
        raise HTTPException(status_code=404, detail="Artifact not found.")
    
    try:
        content = art_file.read_text(encoding="utf-8")
        return Response(content=content, media_type="text/markdown")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

# --- USER PROFILE ENDPOINTS ---

@app.post("/api/profile/import")
def import_local_profile(request: ImportLocalProfileRequest) -> dict[str, Any]:
    res = orchestrator.user_profile.import_zip(request.zip_path)
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res

@app.post("/api/profile/upload")
async def upload_profile_zip(file: UploadFile = File(...)) -> dict[str, Any]:
    dest_dir = PROJECT_ROOT / "Sandbox" / "Imported_Documents"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / file.filename
    
    try:
        with dest_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        res = orchestrator.user_profile.import_zip(dest_path)
        if not res.get("ok"):
            raise HTTPException(status_code=400, detail=res.get("error"))
        return res
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/api/profile/info")
def get_profile_info() -> dict[str, Any]:
    manifest = orchestrator.user_profile.get_manifest()
    profile_dir = orchestrator.user_profile.get_profile_dir()
    
    if not manifest or not profile_dir:
        return {"loaded": False, "message": "No active user profile modules imported."}
        
    return {
        "loaded": True,
        "profile_name": manifest.get("profile_name", "Malik Lloyd User Profile Modules"),
        "version": manifest.get("version", "0.1"),
        "primary_user": manifest.get("primary_user", "Malik Lloyd"),
        "modules": manifest.get("modules", []),
        "recommended_default_modules": manifest.get("recommended_default_modules", [])
    }

@app.get("/api/profile/module/{filename}")
def get_profile_module(filename: str) -> Response:
    content = orchestrator.user_profile.read_module(filename)
    if content.startswith("Error"):
        raise HTTPException(status_code=404, detail=content)
    return Response(content=content, media_type="text/markdown")

@app.post("/api/profile/module/{filename}")
def save_profile_module(filename: str, request: SaveModuleRequest) -> dict[str, Any]:
    ok = orchestrator.user_profile.save_module(filename, request.content)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to save profile module.")
    return {"status": "success"}

@app.post("/api/profile/simulate_route")
def simulate_profile_routing(request: SimulateRouteRequest) -> dict[str, Any]:
    res = orchestrator.user_profile.route_context(request.prompt)
    return {
        "loaded_modules": res.get("loaded_modules", []),
        "matched_keywords": res.get("matched_keywords", {}),
        "context_length_chars": len(res.get("context_block", ""))
    }

# --- ACTIVE N8N REST ENDPOINTS ---

class CreateN8NWorkflowTemplateRequest(BaseModel):
    name: str
    path: str
    action_url: str

class ToggleN8NWorkflowRequest(BaseModel):
    active: bool

@app.get("/api/n8n/workflows")
def list_n8n_workflows() -> dict[str, Any]:
    res = orchestrator.n8n.list_workflows()
    if not res.get("ok"):
        raise HTTPException(status_code=502, detail=res.get("error"))
    return res

@app.get("/api/n8n/workflows/{workflow_id}")
def get_n8n_workflow(workflow_id: str) -> dict[str, Any]:
    res = orchestrator.n8n.get_workflow(workflow_id)
    if not res.get("ok"):
        raise HTTPException(status_code=404, detail=res.get("error"))
    return res

@app.post("/api/n8n/workflows/template")
def create_n8n_workflow_template(request: CreateN8NWorkflowTemplateRequest) -> dict[str, Any]:
    nodes, connections = orchestrator.n8n_manager.compile_webhook_trigger_workflow(
        name=request.name,
        webhook_path=request.path,
        action_url=request.action_url,
        secret_token=orchestrator.n8n.webhook_secret
    )
    res = orchestrator.n8n.create_workflow(name=request.name, nodes=nodes, connections=connections)
    if not res.get("ok"):
        raise HTTPException(status_code=502, detail=res.get("error"))
    return res

@app.post("/api/n8n/workflows/suggestions/council")
def generate_council_n8n_suggestions() -> dict[str, Any]:
    # Formulate a structured prompt for the council to suggest n8n automation nodes
    prompt = (
        "You are the Vaila OS Council. Suggest three highly strategic automation workflows "
        "that integrate Vaila OS with third-party or local services via n8n webhook nodes. "
        "Return a JSON array containing three objects, each with the following exact keys: "
        "\"name\", \"path\", \"action_url\", \"description\". "
        "Return ONLY the raw JSON block without markdown formatting or introductory text."
    )
    envelope = envelope_service.create(user_text=prompt, source="system_agent")
    route = {"task_type": "general_chat", "persona": "proto_jane", "confidence": 1.0}
    try:
        res = orchestrator.handle(envelope=envelope, route=route)
        raw_text = res.visible_text.strip()
        # strip markdown code block tags if present
        if raw_text.startswith("```"):
            lines = raw_text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines[-1].startswith("```"):
                lines = lines[:-1]
            raw_text = "\n".join(lines).strip()
        suggestions = json.loads(raw_text)
        return {"ok": True, "suggestions": suggestions}
    except Exception as exc:
        # Fallback to predefined suggestions if LLM is offline or returns invalid JSON
        return {
            "ok": True,
            "suggestions": [
                {
                    "name": "Council Consensus Streamer",
                    "path": "council-backups",
                    "action_url": "http://localhost:8000/api/backup",
                    "description": "Triggered by Council finalizations to backup synthesized reports to storage."
                },
                {
                    "name": "Memory Review Notifier",
                    "path": "memory-notify",
                    "action_url": "http://localhost:8000/api/memory/notify",
                    "description": "Periodically ping the operator when the Memory Candidates review queue gets populated."
                },
                {
                    "name": "Intrusion Sandbox Alert",
                    "path": "sandbox-alarm",
                    "action_url": "http://localhost:8000/api/sandbox/alert",
                    "description": "Fires when dangerous commands or imports are detected inside the sandbox vault."
                }
            ]
        }

@app.put("/api/n8n/workflows/{workflow_id}/toggle")
def toggle_n8n_workflow(workflow_id: str, request: ToggleN8NWorkflowRequest) -> dict[str, Any]:
    res = orchestrator.n8n.toggle_workflow(workflow_id, request.active)
    if not res.get("ok"):
        raise HTTPException(status_code=502, detail=res.get("error"))
    return res

@app.delete("/api/n8n/workflows/{workflow_id}")
def delete_n8n_workflow(workflow_id: str) -> dict[str, Any]:
    res = orchestrator.n8n.delete_workflow(workflow_id)
    if not res.get("ok"):
        raise HTTPException(status_code=502, detail=res.get("error"))
    return res


# ==============================================================
# --- ADVANCED SYSTEM TOOLS REST ENDPOINTS ---
# ==============================================================

class CreateGoalRequest(BaseModel):
    title: str
    description: str = ""
    status: str = "todo"
    priority: str = "medium"

class CreateSubtaskRequest(BaseModel):
    title: str
    status: str = "todo"

class UpdateSubtaskRequest(BaseModel):
    status: str

class LinkFileRequest(BaseModel):
    file_path: str

class SearchMemoryRequest(BaseModel):
    query: str
    limit: int = 5

class WriteMemoryRequest(BaseModel):
    text: str
    category: str = "general"
    project_only: bool = False


# 1. Tool Registry Inspector Endpoints
@app.get("/api/advanced/registry/audit")
def advanced_registry_audit() -> dict[str, Any]:
    return orchestrator.registry_inspector.run_audit()

@app.get("/api/advanced/registry/report")
def advanced_registry_report() -> Response:
    report = orchestrator.registry_inspector.render_report()
    return Response(content=report, media_type="text/markdown")


# 2. System Dependency Doctor Endpoints
@app.get("/api/advanced/dependency/diagnose")
def advanced_dependency_diagnose() -> dict[str, Any]:
    return orchestrator.dependency_doctor.run_diagnostics()

@app.get("/api/advanced/dependency/report")
def advanced_dependency_report() -> Response:
    report = orchestrator.dependency_doctor.render_report()
    return Response(content=report, media_type="text/markdown")


# 3. Memory Review Console & Adapter Endpoints
@app.get("/api/advanced/memory/candidates")
def advanced_memory_list_candidates() -> list[dict[str, Any]]:
    return orchestrator.memory_review_console.list_reviewable_candidates()

@app.post("/api/advanced/memory/candidates/{cand_id}/edit")
def advanced_memory_edit_candidate(cand_id: str, request: UpdateCandidateRequest) -> dict[str, Any]:
    if request.text is None:
        raise HTTPException(status_code=400, detail="Missing parameter 'text'.")
    ok = orchestrator.memory_review_console.edit_candidate_payload(cand_id, request.text)
    if not ok:
        raise HTTPException(status_code=404, detail="Candidate not found or edit failed.")
    return {"status": "success"}

@app.post("/api/advanced/memory/candidates/{cand_id}/reject")
def advanced_memory_reject_candidate(cand_id: str) -> dict[str, Any]:
    ok = orchestrator.memory_review_console.reject_candidate(cand_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    return {"status": "success"}

@app.post("/api/advanced/memory/candidates/{cand_id}/promote")
def advanced_memory_promote_candidate(cand_id: str, request: DurableMemoryRequest) -> dict[str, Any]:
    res = orchestrator.memory_review_console.promote_candidate(
        cand_id=cand_id,
        category=request.category,
        project_only=request.project_only,
        custom_text=request.text
    )
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res

@app.post("/api/advanced/memory/search")
def advanced_memory_search(request: SearchMemoryRequest) -> list[dict[str, Any]]:
    return orchestrator.memory_adapter.search_memories(query=request.query, limit=request.limit)

@app.post("/api/advanced/memory/write")
def advanced_memory_write(request: WriteMemoryRequest) -> dict[str, Any]:
    res = orchestrator.memory_adapter.write_memory(
        text=request.text,
        category=request.category,
        project_only=request.project_only
    )
    if not res.get("ok"):
        raise HTTPException(status_code=500, detail=res.get("error"))
    return res


# 4. Self-Model Diff Endpoints
@app.get("/api/advanced/self-model/diff")
def advanced_self_model_diff() -> Response:
    report = orchestrator.model_diff_tool.render_diff_report()
    return Response(content=report, media_type="text/markdown")


# 5. Capability Map Endpoints
@app.get("/api/advanced/capability/map")
def advanced_capability_map() -> Response:
    report = orchestrator.capability_map_generator.render_mermaid_flowchart()
    return Response(content=report, media_type="text/markdown")


# 6. Behavior Regression Endpoints
@app.get("/api/advanced/behavior/regression")
def advanced_behavior_regression() -> Response:
    report = orchestrator.behavior_regression_tester.render_regression_report()
    return Response(content=report, media_type="text/markdown")


# 7. Patch Review Endpoints
@app.get("/api/advanced/patch/list")
def advanced_patch_list() -> list[dict[str, Any]]:
    return orchestrator.patch_proposal_reviewer.list_patches()

@app.get("/api/advanced/patch/{filename}/review")
def advanced_patch_review(filename: str) -> Response:
    report = orchestrator.patch_proposal_reviewer.render_review_report(filename)
    return Response(content=report, media_type="text/markdown")

@app.post("/api/advanced/patch/{filename}/apply")
def advanced_patch_apply(filename: str) -> dict[str, Any]:
    res = orchestrator.patch_proposal_reviewer.apply_patch(filename)
    if not res.get("ok"):
        raise HTTPException(status_code=500, detail=res.get("error"))
    return res


# 8. Goal Task Tracking Endpoints
@app.get("/api/advanced/goals/board")
def advanced_goals_board() -> Response:
    report = orchestrator.goal_task_tracker.render_kanban_board()
    return Response(content=report, media_type="text/markdown")

@app.post("/api/advanced/goals/add")
def advanced_goals_add(request: CreateGoalRequest) -> dict[str, Any]:
    return orchestrator.goal_task_tracker.add_goal(
        title=request.title,
        description=request.description,
        status=request.status,
        priority=request.priority
    )

@app.post("/api/advanced/goals/{goal_id}/subtask")
def advanced_goals_add_subtask(goal_id: str, request: CreateSubtaskRequest) -> dict[str, Any]:
    ok = orchestrator.goal_task_tracker.add_subtask(goal_id, request.title, request.status)
    if not ok:
        raise HTTPException(status_code=404, detail="Goal not found.")
    return {"status": "success"}

@app.post("/api/advanced/goals/{goal_id}/subtask/{sub_id}/status")
def advanced_goals_update_subtask(goal_id: str, sub_id: str, request: UpdateSubtaskRequest) -> dict[str, Any]:
    ok = orchestrator.goal_task_tracker.update_subtask_status(goal_id, sub_id, request.status)
    if not ok:
        raise HTTPException(status_code=404, detail="Subtask or Goal not found.")
    return {"status": "success"}


# 9. n8n Workflow Librarian Endpoints
@app.get("/api/advanced/n8n/library")
def advanced_n8n_list_library() -> list[dict[str, Any]]:
    return orchestrator.n8n_workflow_librarian.list_library_workflows()

@app.post("/api/advanced/n8n/import/{workflow_id}")
def advanced_n8n_import_workflow(workflow_id: str) -> dict[str, Any]:
    res = orchestrator.n8n_workflow_librarian.import_workflow_from_n8n(workflow_id)
    if not res.get("ok"):
        raise HTTPException(status_code=500, detail=res.get("error"))
    return res

@app.get("/api/advanced/n8n/document/{filename}")
def advanced_n8n_document_workflow(filename: str) -> Response:
    report = orchestrator.n8n_workflow_librarian.document_workflow(filename)
    return Response(content=report, media_type="text/markdown")


# 10. Safety & Boundary Auditor Endpoints
@app.get("/api/advanced/safety/audit")
def advanced_safety_audit() -> Response:
    report = orchestrator.safety_boundary_auditor.render_safety_report()
    return Response(content=report, media_type="text/markdown")


# 11. Persona Drift Monitor Endpoints
@app.get("/api/advanced/persona/drift")
def advanced_persona_drift() -> Response:
    report = orchestrator.persona_drift_monitor.render_drift_report()
    return Response(content=report, media_type="text/markdown")


# 12. User Profile Telemetry Endpoints
@app.get("/api/advanced/profile/telemetry")
def advanced_profile_telemetry() -> Response:
    report = orchestrator.user_context_router.render_analysis_report()
    return Response(content=report, media_type="text/markdown")


# 13. Self-Evolution Planner Endpoints
@app.get("/api/advanced/evolution/plan")
def advanced_evolution_plan() -> Response:
    report = orchestrator.self_evolution_planner.render_evolution_report()
    return Response(content=report, media_type="text/markdown")


# Run with:
# uvicorn Core_System_Files.local_api:app --reload --host 127.0.0.1 --port 8765
