from __future__ import annotations

import hashlib
import re
from typing import Any

from app.schemas import RequestEnvelope
from app.time_context import utc_now


def normalize_request_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def build_request_envelope(
    original_text: str,
    *,
    response_type: str = "short_text",
    source: str = "chat",
    device_context: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> RequestEnvelope:
    """Create a stable, append-only wrapper around the user request.

    The original_text field is never rewritten. Later systems may add refined
    prompt advice as metadata, but the original request remains authoritative.
    """
    received_at = utc_now()
    normalized = normalize_request_text(original_text)
    raw_id = f"{received_at}|{source}|{response_type}|{original_text}"
    request_id = "req_" + hashlib.sha256(raw_id.encode("utf-8", errors="ignore")).hexdigest()[:18]
    return RequestEnvelope(
        id=request_id,
        original_text=original_text,
        normalized_text=normalized,
        received_at=received_at,
        source=source,
        response_type=response_type,
        device_context=device_context or {},
        metadata=metadata or {},
    )
