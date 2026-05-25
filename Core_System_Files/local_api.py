from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from System_Services.envelope_service import EnvelopeService
from System_Services.logging_service import LoggingService
from System_Services.orchestration_service import OrchestrationService
from System_Services.router_service import RouterService

app = FastAPI(title="Vaila OS V3 Local API & GUI", version="0.2.0")

# Enable CORS for external developers or custom clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = LoggingService(project_root=PROJECT_ROOT)
envelope_service = EnvelopeService(project_root=PROJECT_ROOT)
router = RouterService(project_root=PROJECT_ROOT)
orchestrator = OrchestrationService(project_root=PROJECT_ROOT, logger=logger)


class ChatRequest(BaseModel):
    text: str
    persona: str | None = None
    source: str = "local_api"
    session_id: str | None = None


class ClearRequest(BaseModel):
    session_id: str | None = None


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


# Static asset serving endpoints (Offline-first, Zero-dependency)

@app.get("/")
def serve_index() -> HTMLResponse:
    static_file = PROJECT_ROOT / "Core_System_Files" / "static" / "index.html"
    if static_file.exists():
        return HTMLResponse(content=static_file.read_text(encoding="utf-8"))
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


@app.get("/static/style.css")
def serve_style() -> Response:
    static_file = PROJECT_ROOT / "Core_System_Files" / "static" / "style.css"
    if static_file.exists():
        return Response(content=static_file.read_text(encoding="utf-8"), media_type="text/css")
    return Response(status_code=404)


@app.get("/static/app.js")
def serve_js() -> Response:
    static_file = PROJECT_ROOT / "Core_System_Files" / "static" / "app.js"
    if static_file.exists():
        return Response(content=static_file.read_text(encoding="utf-8"), media_type="application/javascript")
    return Response(status_code=404)


# Telemetry and Operational endpoints

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
    return {"summary": summary}


@app.post("/api/reports/self_assessment")
def run_self_assessment() -> dict[str, Any]:
    report = orchestrator.self_assessment.run_self_assessment()
    return {"report": report}


@app.post("/chat")
def chat(request: ChatRequest) -> dict[str, Any]:
    text = request.text
    if request.persona:
        # Prepend persona context identifier if explicitly chosen
        text = f"{request.persona}, {text}"

    # If selected_persona is in request, let's insert it in envelope metadata
    metadata = {
        "interface": "web_client",
        "selected_persona": request.persona or "proto_jane",
        "session_id": request.session_id or "web_session",
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


# Run with:
# uvicorn Core_System_Files.local_api:app --reload --host 127.0.0.1 --port 8765
