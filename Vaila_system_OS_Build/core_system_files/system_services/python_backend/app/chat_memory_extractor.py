from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

from app.router import detect_addressed_persona, normalize_text
from app.schemas import MemoryCandidate, RoutePlan


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_hash(text: str, length: int = 18) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:length]


MEMORY_CUE_PATTERNS = [
    r"\bplease\s+update\s+(?:your|the)\s+memory\b",
    r"\bupdate\s+(?:your|the)\s+memory\b",
    r"\bremember\s+that\b",
    r"\bplease\s+remember\b",
    r"\badd\s+this\s+to\s+memory\b",
    r"\bsave\s+this\s+to\s+memory\b",
    r"\bcommit\s+this\s+to\s+memory\b",
    r"\bstore\s+this\s+in\s+memory\b",
    r"\bnote\s+that\b",
]


def extract_chat_memory_candidates(user_text: str, route_plan: RoutePlan | None = None) -> list[MemoryCandidate]:
    """Create reviewable memory candidates from explicit chat memory requests.

    This module intentionally does not write memory directly. It only creates
    pending candidates so the user can approve or reject them in the existing
    review workflow.
    """

    cleaned = _strip_addressed_persona(user_text)
    normalized = normalize_text(cleaned)

    if not _has_memory_cue(normalized) and not _looks_like_explicit_project_status_fact(normalized):
        return []

    candidate_text = _extract_candidate_text(cleaned)
    if not candidate_text:
        return []

    candidate = _build_candidate(candidate_text, user_text, route_plan)
    return [candidate]


def _strip_addressed_persona(text: str) -> str:
    normalized = normalize_text(text)
    addressed = detect_addressed_persona(normalized)
    if not addressed:
        return text.strip()
    return re.sub(r"^\s*[^,;:\-]+\s*[,;:\-]\s*", "", text.strip(), count=1)


def _has_memory_cue(normalized_text: str) -> bool:
    return any(re.search(pattern, normalized_text) for pattern in MEMORY_CUE_PATTERNS)


def _looks_like_explicit_project_status_fact(normalized_text: str) -> bool:
    if "phase" not in normalized_text:
        return False
    status_terms = [
        "we are currently",
        "we're currently",
        "project vaila is currently",
        "vaila is currently",
        "current phase",
        "currently in phase",
        "currently in the",
    ]
    return any(term in normalized_text for term in status_terms)


def _extract_candidate_text(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return ""

    # For messages like "Please update your memory. We are currently...",
    # preserve the fact after the cue sentence rather than the cue itself.
    sentences = _split_sentences(stripped)
    if len(sentences) > 1 and _has_memory_cue(normalize_text(sentences[0])):
        return " ".join(sentences[1:]).strip()

    # For messages like "Remember that Vaila is...", remove the cue prefix.
    for pattern in MEMORY_CUE_PATTERNS:
        match = re.search(pattern, normalize_text(stripped))
        if match:
            # Use the matched text position from a case-insensitive search on the original string.
            original_match = re.search(pattern, stripped, flags=re.IGNORECASE)
            if original_match:
                return stripped[original_match.end():].lstrip(" .:-").strip()

    return stripped


def _split_sentences(text: str) -> list[str]:
    # Good enough for short control-panel chat messages. Avoids external deps.
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [part.strip() for part in parts if part.strip()]


def _build_candidate(candidate_text: str, user_text: str, route_plan: RoutePlan | None) -> MemoryCandidate:
    normalized = normalize_text(candidate_text)
    created_at = utc_now()
    tags = ["chat_memory", "user_requested", "review_required"]
    persona_scope = ["all"]
    confidence = "medium"
    question = "What did Malik ask Vaila to remember from chat?"
    answer = candidate_text.strip()

    phase_match = re.search(r"\b(?:phase|phase\s*)\s*([0-6])\b", normalized)
    if phase_match and ("vaila" in normalized or "we are" in normalized or "project vaila" in normalized or "phase" in normalized):
        phase_number = phase_match.group(1)
        tags.extend(["project_vaila", "current_phase", f"phase_{phase_number}"])
        if "system intelligence" in normalized:
            tags.append("system_intelligence")
        if "late" in normalized:
            tags.append("late_phase")
        confidence = "high"
        question = "What phase is Project Vaila currently in?"
        answer = _clean_phase_answer(candidate_text)

    if route_plan:
        if route_plan.persona and route_plan.persona not in persona_scope:
            # Scope stays all, but the tag helps trace which persona the update was addressed through.
            tags.append(route_plan.persona)
        if route_plan.task_type:
            tags.append(route_plan.task_type)

    tags = _dedupe(tags)
    raw_id = f"chat_memory|{question}|{answer}|{','.join(tags)}"

    return MemoryCandidate(
        id=f"candidate_chat_{stable_hash(raw_id)}",
        question=question,
        answer=answer,
        tags=tags,
        persona_scope=persona_scope,
        confidence=confidence,
        source_type="chat_memory_candidate",
        source_document_id="",
        source_path="chat://desktop-client",
        source_title="Chat memory request",
        chunk_ids=[f"chat_{stable_hash(user_text, 12)}"],
        status="pending",
        created_at=created_at,
    )


def _clean_phase_answer(candidate_text: str) -> str:
    cleaned = candidate_text.strip()
    cleaned = re.sub(r"\bwe\s+are\b", "Project Vaila is", cleaned, count=1, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bwe're\b", "Project Vaila is", cleaned, count=1, flags=re.IGNORECASE)
    return cleaned


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        clean = value.strip()
        if clean and clean not in seen:
            result.append(clean)
            seen.add(clean)
    return result
