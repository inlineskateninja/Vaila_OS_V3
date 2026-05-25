from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from System_Services.voice_command_normalizer import normalize_voice_transcript


@dataclass
class ToolIntent:
    intent_id: str
    tool_id: str
    service_id: str
    action: str
    confidence: float
    risk_level: str
    approval_required: bool
    source: str
    raw_text: str
    normalized_text: str
    entities: dict[str, Any] = field(default_factory=dict)
    matched_patterns: list[str] = field(default_factory=list)
    needs_clarification: bool = False
    clarification_question: str = ""


class ToolIntentService:
    """
    Deterministic assistant tool intent detector.

    This service identifies likely assistant tool intents, but it does not
    execute tools or call an LLM. Runtime routing can opt into this later.
    """

    FALLBACK_INTENT_ID = "general_chat"
    FALLBACK_TOOL_ID = "general_chat"

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.registry_dir = project_root / "Tools_Registry"
        self.intent_registry = self.load_intent_registry()

    def normalize_text(self, text: str) -> str:
        lowered = text.lower().strip()
        lowered = re.sub(r"[^\w\s:%$./@+-]", " ", lowered)
        return re.sub(r"\s+", " ", lowered).strip()

    def detect_intent(self, text: str, source: str = "text") -> ToolIntent:
        candidates = self.detect_candidates(text=text, source=source)
        if candidates:
            return candidates[0]
        return self._fallback_intent(text=text, source=source)

    def detect_candidates(self, text: str, source: str = "text") -> list[ToolIntent]:
        prepared = self._prepare_text(text=text, source=source)
        raw_text = prepared["raw_text"]
        normalized = prepared["normalized_text"]
        candidates = self.match_pattern_intents(text=raw_text, normalized_text=normalized, source=source)
        candidates.extend(self.match_keyword_intents(text=raw_text, normalized_text=normalized, source=source))

        if prepared["voice_metadata"]:
            for candidate in candidates:
                candidate.entities["voice"] = prepared["voice_metadata"]

        deduped: dict[tuple[str, str], ToolIntent] = {}
        for candidate in candidates:
            key = (candidate.tool_id, candidate.action)
            existing = deduped.get(key)
            if existing is None or candidate.confidence > existing.confidence:
                deduped[key] = candidate

        ranked = sorted(
            deduped.values(),
            key=lambda item: (item.confidence, -item.needs_clarification),
            reverse=True,
        )
        return ranked

    def _prepare_text(self, text: str, source: str) -> dict[str, Any]:
        if source != "voice_stt":
            return {
                "raw_text": text,
                "normalized_text": self.normalize_text(text),
                "voice_metadata": {},
            }

        voice = normalize_voice_transcript(text)
        return {
            "raw_text": voice["raw_transcript"],
            "normalized_text": self.normalize_text(voice["normalized_text"]),
            "voice_metadata": voice,
        }

    def load_intent_registry(self) -> dict[str, Any]:
        tools_data = self._load_json(self.registry_dir / "assistant_tools.json")
        intents_data = self._load_json(self.registry_dir / "assistant_tool_intents.json")
        routes_data = self._load_json(self.registry_dir / "assistant_tool_routes.json")

        tools = tools_data.get("tools", []) if isinstance(tools_data, dict) else []
        tool_map = {
            tool["tool_id"]: tool
            for tool in tools
            if isinstance(tool, dict) and isinstance(tool.get("tool_id"), str)
        }

        return {
            "tools": tool_map,
            "intents": intents_data.get("intents", {}) if isinstance(intents_data, dict) else {},
            "routes": routes_data.get("routes", {}) if isinstance(routes_data, dict) else {},
        }

    def match_pattern_intents(self, text: str, normalized_text: str | None = None, source: str = "text") -> list[ToolIntent]:
        normalized = normalized_text or self.normalize_text(text)
        candidates: list[ToolIntent] = []

        for rule in self._pattern_rules():
            matched = [pattern for pattern in rule["patterns"] if re.search(pattern, normalized)]
            if not matched:
                continue
            entities = self._extract_entities(normalized, rule["tool_id"], rule["action"])
            candidates.append(
                self._build_intent(
                    intent_id=rule["intent_id"],
                    tool_id=rule["tool_id"],
                    action=rule["action"],
                    confidence=rule["confidence"],
                    source=source,
                    raw_text=text,
                    normalized_text=normalized,
                    matched_patterns=matched,
                    entities=entities,
                )
            )

        return candidates

    def match_keyword_intents(self, text: str, normalized_text: str | None = None, source: str = "text") -> list[ToolIntent]:
        normalized = normalized_text or self.normalize_text(text)
        candidates: list[ToolIntent] = []

        for rule in self._keyword_rules():
            service_hits = self._count_hits(normalized, rule["service_terms"])
            action_hits = self._count_hits(normalized, rule["action_terms"])
            alias_hits = self._count_hits(normalized, rule["aliases"])

            if not alias_hits and not (service_hits and action_hits):
                continue

            confidence = min(0.86, 0.42 + (service_hits * 0.12) + (action_hits * 0.12) + (alias_hits * 0.16))
            matched = [
                term
                for term in [*rule["service_terms"], *rule["action_terms"], *rule["aliases"]]
                if self._term_matches(normalized, term)
            ]
            entities = self._extract_entities(normalized, rule["tool_id"], rule["action"])
            candidates.append(
                self._build_intent(
                    intent_id=rule["intent_id"],
                    tool_id=rule["tool_id"],
                    action=rule["action"],
                    confidence=confidence,
                    source=source,
                    raw_text=text,
                    normalized_text=normalized,
                    matched_patterns=matched,
                    entities=entities,
                )
            )

        return candidates

    def _build_intent(
        self,
        intent_id: str,
        tool_id: str,
        action: str,
        confidence: float,
        source: str,
        raw_text: str,
        normalized_text: str,
        matched_patterns: list[str],
        entities: dict[str, Any],
    ) -> ToolIntent:
        tool = self.intent_registry["tools"].get(tool_id, {})
        service_id = tool.get("service_id", "")
        risk_level = tool.get("risk_levels", {}).get(action, "unknown")
        approval_required = action in tool.get("approval_required_actions", [])
        needs_clarification, question = self._clarification_state(tool_id, action, normalized_text, entities)

        return ToolIntent(
            intent_id=intent_id,
            tool_id=tool_id,
            service_id=service_id,
            action=action,
            confidence=round(confidence, 3),
            risk_level=risk_level,
            approval_required=approval_required,
            source=source,
            raw_text=raw_text,
            normalized_text=normalized_text,
            entities=entities,
            matched_patterns=matched_patterns,
            needs_clarification=needs_clarification,
            clarification_question=question,
        )

    def _fallback_intent(self, text: str, source: str) -> ToolIntent:
        prepared = self._prepare_text(text=text, source=source)
        normalized = prepared["normalized_text"]
        entities = {"voice": prepared["voice_metadata"]} if prepared["voice_metadata"] else {}
        return ToolIntent(
            intent_id=self.FALLBACK_INTENT_ID,
            tool_id=self.FALLBACK_TOOL_ID,
            service_id="assistant",
            action="chat",
            confidence=0.0,
            risk_level="low",
            approval_required=False,
            source=source,
            raw_text=text,
            normalized_text=normalized,
            entities=entities,
            matched_patterns=[],
            needs_clarification=False,
            clarification_question="",
        )

    def _pattern_rules(self) -> list[dict[str, Any]]:
        return [
            {
                "intent_id": "calendar_management",
                "tool_id": "google_calendar",
                "action": "create_event",
                "confidence": 0.96,
                "patterns": [
                    r"\b(schedule|book|add|create|set up)\b.*\b(meeting|event|appointment|call|focus block)\b",
                    r"\bput\b.*\bon my calendar\b",
                ],
            },
            {
                "intent_id": "calendar_management",
                "tool_id": "google_calendar",
                "action": "list_events",
                "confidence": 0.93,
                "patterns": [
                    r"\b(what'?s|what s|what is|show|list|check)\b.*\b(calendar|schedule|agenda)\b",
                    r"\b(calendar|schedule|agenda)\b.*\b(today|tomorrow|this week|next week)\b",
                ],
            },
            {
                "intent_id": "email_management",
                "tool_id": "gmail",
                "action": "draft_reply",
                "confidence": 0.95,
                "patterns": [
                    r"\b(draft|write|compose)\b.*\b(reply|email|message)\b",
                    r"\b(reply)\b.*\b(email|gmail|thread)\b",
                ],
            },
            {
                "intent_id": "drive_file_management",
                "tool_id": "google_drive",
                "action": "search_files",
                "confidence": 0.92,
                "patterns": [
                    r"\b(find|search|locate|look for)\b.*\b(drive|google drive|doc|document|file|folder|pdf)\b",
                    r"\b(drive|google drive)\b.*\b(file|doc|document|folder)\b",
                ],
            },
            {
                "intent_id": "task_management",
                "tool_id": "google_tasks",
                "action": "create_task",
                "confidence": 0.94,
                "patterns": [
                    r"\b(add|create|make|set)\b.*\b(task|to do|todo)\b",
                    r"\b(task me|add to my tasks)\b",
                ],
            },
            {
                "intent_id": "contact_lookup",
                "tool_id": "google_people",
                "action": "search_contacts",
                "confidence": 0.91,
                "patterns": [
                    r"\b(find|look up|search)\b.*\b(contact|contacts|phone number|email address)\b",
                    r"\b(contact|contacts)\b.*\b(for|named|called)\b",
                ],
            },
            {
                "intent_id": "note_capture",
                "tool_id": "notes",
                "action": "create_note",
                "confidence": 0.94,
                "patterns": [
                    r"\b(take|create|write|save)\b.*\b(note)\b",
                    r"\b(note that|make a note|jot down)\b",
                ],
            },
            {
                "intent_id": "reminder_management",
                "tool_id": "reminders",
                "action": "create_reminder",
                "confidence": 0.95,
                "patterns": [
                    r"\b(remind me|set a reminder|create a reminder)\b",
                    r"\b(reminder)\b.*\b(to|for|about)\b",
                ],
            },
            {
                "intent_id": "web_research",
                "tool_id": "web_research",
                "action": "search_web",
                "confidence": 0.9,
                "patterns": [
                    r"\b(research|look up|search the web|google|find sources|find official docs)\b",
                    r"\b(current|latest|recent)\b.*\b(info|information|news|docs|source|sources)\b",
                ],
            },
            {
                "intent_id": "calculation",
                "tool_id": "calculator",
                "action": "calculate",
                "confidence": 0.93,
                "patterns": [
                    r"\b(calculate|what is|what's|convert|how many|how much)\b.*\d",
                    r"\d+\s*(%|percent|plus|minus|times|x|\*|/|\+|-)\s*\d+",
                ],
            },
        ]

    def _keyword_rules(self) -> list[dict[str, Any]]:
        return [
            {
                "intent_id": "calendar_management",
                "tool_id": "google_calendar",
                "action": "create_event",
                "service_terms": ["calendar", "schedule", "agenda"],
                "action_terms": ["schedule", "book", "create", "add", "move"],
                "aliases": ["meeting", "appointment", "event", "focus block"],
            },
            {
                "intent_id": "email_management",
                "tool_id": "gmail",
                "action": "draft_reply",
                "service_terms": ["gmail", "email", "inbox", "thread"],
                "action_terms": ["draft", "write", "compose", "reply"],
                "aliases": ["message"],
            },
            {
                "intent_id": "drive_file_management",
                "tool_id": "google_drive",
                "action": "search_files",
                "service_terms": ["drive", "google drive", "doc", "document", "file", "folder"],
                "action_terms": ["find", "search", "locate", "look for"],
                "aliases": ["pdf"],
            },
            {
                "intent_id": "task_management",
                "tool_id": "google_tasks",
                "action": "create_task",
                "service_terms": ["task", "tasks", "todo", "to do"],
                "action_terms": ["add", "create", "make", "set"],
                "aliases": ["google tasks"],
            },
            {
                "intent_id": "contact_lookup",
                "tool_id": "google_people",
                "action": "search_contacts",
                "service_terms": ["contact", "contacts", "people"],
                "action_terms": ["find", "lookup", "look up", "search"],
                "aliases": ["phone number", "email address"],
            },
            {
                "intent_id": "note_capture",
                "tool_id": "notes",
                "action": "create_note",
                "service_terms": ["note", "notes"],
                "action_terms": ["take", "create", "write", "save"],
                "aliases": ["note that", "make a note", "jot down"],
            },
            {
                "intent_id": "reminder_management",
                "tool_id": "reminders",
                "action": "create_reminder",
                "service_terms": ["reminder", "reminders"],
                "action_terms": ["remind", "set", "create"],
                "aliases": ["remind me", "follow up"],
            },
            {
                "intent_id": "web_research",
                "tool_id": "web_research",
                "action": "search_web",
                "service_terms": ["web", "internet", "source", "sources", "docs"],
                "action_terms": ["research", "search", "lookup", "look up", "find"],
                "aliases": ["latest", "current", "official docs"],
            },
            {
                "intent_id": "calculation",
                "tool_id": "calculator",
                "action": "calculate",
                "service_terms": ["calculator", "math", "percent", "%"],
                "action_terms": ["calculate", "convert", "compare"],
                "aliases": ["how many", "how much", "what is"],
            },
        ]

    def _extract_entities(self, normalized: str, tool_id: str, action: str) -> dict[str, Any]:
        entities: dict[str, Any] = {}

        date_terms = ["today", "tomorrow", "tonight", "this week", "next week", "friday", "monday"]
        matched_dates = [term for term in date_terms if self._term_matches(normalized, term)]
        if matched_dates:
            entities["date_terms"] = matched_dates

        time_matches = re.findall(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)?\b", normalized)
        if time_matches:
            entities["time_or_number_terms"] = time_matches

        if tool_id == "gmail":
            email_matches = re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", normalized)
            if email_matches:
                entities["email_addresses"] = email_matches

        if tool_id == "calculator":
            entities["numbers"] = re.findall(r"\d+(?:\.\d+)?", normalized)

        if action.startswith("create_") or action in {"draft_reply", "search_files", "search_contacts"}:
            entities["subject_preview"] = normalized[:160]

        return entities

    def _clarification_state(
        self,
        tool_id: str,
        action: str,
        normalized: str,
        entities: dict[str, Any],
    ) -> tuple[bool, str]:
        if tool_id == "google_calendar" and action == "create_event":
            if "date_terms" not in entities and "time_or_number_terms" not in entities:
                return True, "When should I schedule this calendar event?"

        if tool_id == "reminders" and action == "create_reminder":
            if "date_terms" not in entities and "time_or_number_terms" not in entities:
                return True, "When should I remind you?"

        if tool_id == "google_tasks" and action == "create_task" and normalized in {"add a task", "create task"}:
            return True, "What should the task say?"

        return False, ""

    def _count_hits(self, normalized: str, terms: list[str]) -> int:
        return sum(1 for term in terms if self._term_matches(normalized, term))

    def _term_matches(self, normalized: str, term: str) -> bool:
        if re.search(r"[^\w\s]", term):
            return term in normalized
        return bool(re.search(rf"\b{re.escape(term)}\b", normalized))

    def _load_json(self, path: Path) -> Any:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
