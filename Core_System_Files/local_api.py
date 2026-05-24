from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from System_Services.envelope_service import EnvelopeService
from System_Services.logging_service import LoggingService
from System_Services.orchestration_service import OrchestrationService
from System_Services.router_service import RouterService

app = FastAPI(title="Vaila OS V3 Local API", version="0.1.0")

logger = LoggingService(project_root=PROJECT_ROOT)
envelope_service = EnvelopeService(project_root=PROJECT_ROOT)
router = RouterService(project_root=PROJECT_ROOT)
orchestrator = OrchestrationService(project_root=PROJECT_ROOT, logger=logger)


class ChatRequest(BaseModel):
    text: str
    persona: str | None = None
    source: str = "local_api"


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "project_root": str(PROJECT_ROOT),
    }


@app.post("/chat")
def chat(request: ChatRequest) -> dict[str, Any]:
    text = request.text
    if request.persona:
        text = f"{request.persona}, {text}"

    envelope = envelope_service.create(user_text=text, source=request.source)
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


# Run with:
# uvicorn Core_System_Files.local_api:app --reload --host 127.0.0.1 --port 8765
