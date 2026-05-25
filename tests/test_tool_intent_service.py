from __future__ import annotations

from pathlib import Path

from System_Services.router_service import RouterService
from System_Services.tool_intent_service import ToolIntentService
from System_Services.voice_command_normalizer import normalize_voice_transcript


def make_service() -> ToolIntentService:
    return ToolIntentService(project_root=Path(__file__).resolve().parents[1])


def test_calendar_create_event_prompt() -> None:
    intent = make_service().detect_intent("Schedule a project meeting tomorrow at 2 PM.")

    assert intent.intent_id == "calendar_management"
    assert intent.tool_id == "google_calendar"
    assert intent.service_id == "google"
    assert intent.action == "create_event"
    assert intent.risk_level == "high"
    assert intent.approval_required is True
    assert intent.confidence > 0.9
    assert intent.entities["date_terms"] == ["tomorrow"]


def test_calendar_read_prompt() -> None:
    intent = make_service().detect_intent("What is on my calendar today?")

    assert intent.intent_id == "calendar_management"
    assert intent.tool_id == "google_calendar"
    assert intent.action == "list_events"
    assert intent.risk_level == "medium"
    assert intent.approval_required is False


def test_gmail_draft_prompt() -> None:
    intent = make_service().detect_intent("Draft a reply to the email saying I can meet next week.")

    assert intent.intent_id == "email_management"
    assert intent.tool_id == "gmail"
    assert intent.action == "draft_reply"
    assert intent.service_id == "google"
    assert intent.approval_required is False


def test_drive_search_prompt() -> None:
    intent = make_service().detect_intent("Find the latest Vaila roadmap document in Google Drive.")

    assert intent.intent_id == "drive_file_management"
    assert intent.tool_id == "google_drive"
    assert intent.action == "search_files"
    assert intent.risk_level == "medium"


def test_tasks_create_prompt() -> None:
    intent = make_service().detect_intent("Add a task to review the assistant registry tonight.")

    assert intent.intent_id == "task_management"
    assert intent.tool_id == "google_tasks"
    assert intent.action == "create_task"
    assert intent.approval_required is True


def test_contacts_lookup_prompt() -> None:
    intent = make_service().detect_intent("Look up Alex in my contacts.")

    assert intent.intent_id == "contact_lookup"
    assert intent.tool_id == "google_people"
    assert intent.action == "search_contacts"
    assert intent.service_id == "google"


def test_notes_create_prompt() -> None:
    intent = make_service().detect_intent("Take a note that intent detection is deterministic.")

    assert intent.intent_id == "note_capture"
    assert intent.tool_id == "notes"
    assert intent.action == "create_note"
    assert intent.service_id == "local_assistant"


def test_reminder_create_prompt() -> None:
    intent = make_service().detect_intent("Remind me to test the app tomorrow morning.")

    assert intent.intent_id == "reminder_management"
    assert intent.tool_id == "reminders"
    assert intent.action == "create_reminder"
    assert intent.approval_required is True
    assert intent.needs_clarification is False


def test_web_search_prompt() -> None:
    intent = make_service().detect_intent("Research the latest official docs for Google Calendar API scopes.")

    assert intent.intent_id == "web_research"
    assert intent.tool_id == "web_research"
    assert intent.action == "search_web"
    assert intent.risk_level == "low"


def test_calculator_prompt() -> None:
    intent = make_service().detect_intent("What is 22 percent of 180?")

    assert intent.intent_id == "calculation"
    assert intent.tool_id == "calculator"
    assert intent.action == "calculate"
    assert intent.entities["numbers"] == ["22", "180"]


def test_general_chat_should_not_trigger_tool() -> None:
    intent = make_service().detect_intent("How are you feeling about the system design today?")

    assert intent.intent_id == "general_chat"
    assert intent.tool_id == "general_chat"
    assert intent.action == "chat"
    assert intent.confidence == 0.0
    assert intent.matched_patterns == []


def test_voice_reminder_create_prompt() -> None:
    intent = make_service().detect_intent(
        "Vaila remind me tomorrow to check the assistant registry.",
        source="voice_stt",
    )

    assert intent.intent_id == "reminder_management"
    assert intent.tool_id == "reminders"
    assert intent.action == "create_reminder"
    assert intent.source == "voice_stt"
    assert intent.raw_text.startswith("Vaila")
    assert intent.normalized_text.startswith("remind me tomorrow")
    assert intent.entities["voice"]["wake_word_detected"] is True
    assert intent.entities["voice"]["persona_hint"] == "proto_jane"


def test_voice_calendar_read_prompt() -> None:
    intent = make_service().detect_intent("Jane what's on my calendar today", source="voice_stt")

    assert intent.intent_id == "calendar_management"
    assert intent.tool_id == "google_calendar"
    assert intent.action == "list_events"
    assert intent.entities["voice"]["persona_hint"] == "proto_jane"


def test_voice_serren_write_this_down_prompt() -> None:
    intent = make_service().detect_intent("Serren write this down intent routing is ready.", source="voice_stt")

    assert intent.intent_id == "note_capture"
    assert intent.tool_id == "notes"
    assert intent.action == "create_note"
    assert intent.normalized_text.startswith("take a note")
    assert intent.entities["voice"]["persona_hint"] == "serren"


def test_voice_vecht_add_task_prompt() -> None:
    intent = make_service().detect_intent("Vecht add a task to test voice mode tonight.", source="voice_stt")

    assert intent.intent_id == "task_management"
    assert intent.tool_id == "google_tasks"
    assert intent.action == "create_task"
    assert intent.entities["voice"]["persona_hint"] == "vecht"


def test_voice_send_email_routes_to_draft_first() -> None:
    intent = make_service().detect_intent(
        "Vaila send an email to Malik saying the registry is ready.",
        source="voice_stt",
    )

    assert intent.intent_id == "email_management"
    assert intent.tool_id == "gmail"
    assert intent.action == "draft_reply"
    assert intent.approval_required is False
    assert "draft an email" in intent.normalized_text


def test_voice_normalizer_returns_metadata() -> None:
    result = normalize_voice_transcript("Jane put this on my calendar tomorrow at two pm")

    assert result == {
        "raw_transcript": "Jane put this on my calendar tomorrow at two pm",
        "normalized_text": "schedule this calendar event tomorrow at 2 pm",
        "wake_word_detected": True,
        "persona_hint": "proto_jane",
        "confidence_notes": ["wake_prefix:jane", "voice_phrase_rewrite:schedule this calendar event"],
    }


def test_existing_router_service_still_works() -> None:
    router = RouterService(project_root=Path(__file__).resolve().parents[1])

    assert router.task_patterns["general_chat"] == r".*"
