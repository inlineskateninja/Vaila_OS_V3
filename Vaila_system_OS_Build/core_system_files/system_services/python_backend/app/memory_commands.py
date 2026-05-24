from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.memory_taxonomy import categorize_memory
from app.schemas import MemoryCandidate, RoutePlan


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_hash(text: str, length: int = 18) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:length]


@dataclass
class MemoryCommand:
    name: str
    description: str
    examples: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "description": self.description, "examples": self.examples}


COMMANDS = [
    MemoryCommand("update memory", "Create a pending memory candidate from the current message.", ["Update memory: Project Vaila is in late Phase 1."]),
    MemoryCommand("propose memories from chat", "Review recent chat activity and create pending memory candidates for durable facts.", ["Propose memories from chat", "Propose memories from the last 10 chats"]),
    MemoryCommand("delete memories of <topic>", "Find memories matching a topic and create a safe deletion review report. Does not delete directly.", ["Delete memories of old Phase 0 status"]),
    MemoryCommand("search memory <topic>", "Search approved memory records by topic.", ["Search memory current phase"]),
    MemoryCommand("list personas", "List installed personas from the persona library.", ["Name all personas", "List installed personas"]),
    MemoryCommand("retain conversation", "At exit, review the session and propose memories before closing.", ["Retain this conversation"]),
]

MEMORY_CUE_PATTERNS = [
    r"\bplease\s+update\s+(?:your|the)?\s*memory\b",
    r"\bupdate\s+(?:your|the)?\s*memory\b",
    r"\bremember\s+that\b",
    r"\bplease\s+remember\b",
    r"\badd\s+this\s+to\s+memory\b",
    r"\bsave\s+this\s+to\s+memory\b",
    r"\bcommit\s+this\s+to\s+memory\b",
    r"\bstore\s+this\s+in\s+memory\b",
    r"\bnote\s+that\b",
]


def command_list() -> list[dict[str, Any]]:
    return [command.to_dict() for command in COMMANDS]


def is_memory_command(text: str) -> bool:
    normalized = text.lower()
    if any(re.search(pattern, normalized) for pattern in MEMORY_CUE_PATTERNS):
        return True
    return any(phrase in normalized for phrase in ["propose memories from chat", "delete memories of", "search memory", "retain conversation"])


def extract_memory_candidates(user_text: str, route_plan: RoutePlan | None = None) -> list[MemoryCandidate]:
    text = _strip_addressed_persona(user_text.strip())
    lower = text.lower()
    if not any(re.search(pattern, lower) for pattern in MEMORY_CUE_PATTERNS):
        return []
    fact = _remove_memory_cue(text)
    if not fact:
        return []
    return [_candidate_from_fact(fact, user_text, route_plan)]


def _candidate_from_fact(fact: str, source_text: str, route_plan: RoutePlan | None = None) -> MemoryCandidate:
    tags = ["chat_memory", "user_requested", "review_required"]
    lower = fact.lower()
    question = "What did Malik ask Vaila to remember from chat?"
    if "phase" in lower and "vaila" in lower or ("phase" in lower and "currently" in lower):
        question = "What phase is Project Vaila currently in?"
        tags.extend(["project_vaila", "current_phase"])
        match = re.search(r"phase\s*([0-6])", lower)
        if match:
            tags.append(f"phase_{match.group(1)}")
        if "system intelligence" in lower:
            tags.append("system_intelligence")
        if "late" in lower:
            tags.append("late_phase")
    category = categorize_memory(question, fact, tags)
    if category not in tags:
        tags.append(category)
    if route_plan:
        tags.append(route_plan.task_type)
        tags.append(route_plan.persona)
    tags = _dedupe(tags)
    cid = f"candidate_chat_{stable_hash(question + fact + ','.join(tags))}"
    return MemoryCandidate(
        id=cid,
        question=question,
        answer=_normalize_fact(fact),
        tags=tags,
        persona_scope=["all"],
        confidence="high" if "current_phase" in tags else "medium",
        source_type="chat_memory_candidate",
        source_path="chat://conversation",
        source_title="Chat memory request",
        chunk_ids=[f"chat_{stable_hash(source_text, 12)}"],
        status="pending",
        created_at=utc_now(),
        category=category,
    )


def candidate_from_activity(event: dict[str, Any]) -> MemoryCandidate | None:
    details = event.get("details", {})
    user_text = details.get("user_text") or event.get("summary", "")
    response_excerpt = details.get("response_excerpt", "")
    text = f"User: {user_text}\nResponse: {response_excerpt}".strip()
    if len(text) < 80:
        return None
    question = f"What useful chat context was captured on {event.get('created_at', '')}?"
    answer = text[:1200]
    tags = ["chat_review", "candidate_from_chat", details.get("task_type", "general"), details.get("persona", "proto_jane")]
    category = categorize_memory(question, answer, tags)
    if category not in tags:
        tags.append(category)
    return MemoryCandidate(
        id=f"candidate_chat_review_{stable_hash(question + answer)}",
        question=question,
        answer=answer,
        tags=_dedupe(tags),
        persona_scope=["all"],
        confidence="low",
        source_type="chat_review_candidate",
        source_path="activity://chat",
        source_title="Recent chat review",
        chunk_ids=[event.get("id", "activity_event")],
        status="pending",
        created_at=utc_now(),
        category=category,
    )


def _strip_addressed_persona(text: str) -> str:
    return re.sub(r"^\s*[^,;:\-]+\s*[,;:\-]\s*", "", text, count=1)


def _remove_memory_cue(text: str) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    if len(sentences) > 1 and any(re.search(pattern, sentences[0].lower()) for pattern in MEMORY_CUE_PATTERNS):
        return " ".join(sentences[1:]).strip()
    for pattern in MEMORY_CUE_PATTERNS:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return text[match.end():].lstrip(" .:-").strip()
    return text.strip()


def _normalize_fact(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^we\s+are\b", "Project Vaila is", text, flags=re.IGNORECASE)
    text = re.sub(r"^we're\b", "Project Vaila is", text, flags=re.IGNORECASE)
    return text


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if not value:
            continue
        clean = str(value).strip().lower().replace(" ", "_")
        if clean and clean not in seen:
            result.append(clean)
            seen.add(clean)
    return result
