from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.persona_continuity import PERSONA_DISPLAY_NAMES


SHORT_TEXT = "short_text"
LONG_TEXT = "long_text"
SHORT_VOICE = "short_voice"
LONG_VOICE = "long_voice"
TEXT_DEBUG = "text_debug"
VOICE_DEBUG = "voice_debug"

ALLOWED_RESPONSE_TYPES = {SHORT_TEXT, LONG_TEXT, SHORT_VOICE, LONG_VOICE, TEXT_DEBUG, VOICE_DEBUG}

DISPLAY_RESPONSE_TYPES = {
    SHORT_TEXT: "Short Text",
    LONG_TEXT: "Long Text",
    SHORT_VOICE: "Short Voice",
    LONG_VOICE: "Long Voice",
    TEXT_DEBUG: "Text with Debug Info",
    VOICE_DEBUG: "Voice with Debug Info",
}

VOICE_PROFILE_BY_PERSONA = {
    "serren": "serren_default",
    "vecht": "vecht_default",
    "riven": "riven_default",
    "maelith": "maelith_default",
    "proto_jane": "proto_jane_default",
    "council": "proto_jane_default",
}


@dataclass
class ResponseRoute:
    response_type: str
    output_channel: str
    should_prepare_tts: bool
    tts_engine: str
    fallback_tts_engine: str
    voice_profile_id: str
    instructions: str
    persona_id: str = "proto_jane"
    persona_display_name: str = "Proto Jane"
    include_debug_info: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_response_type(value: str | None) -> str:
    cleaned = (value or SHORT_TEXT).strip().lower().replace(" ", "_").replace("-", "_").replace("+", "_")
    aliases = {
        "text": LONG_TEXT,
        "text_only": LONG_TEXT,
        "brief_text": SHORT_TEXT,
        "full_text": LONG_TEXT,
        "verbose_text": LONG_TEXT,
        "debug_text": TEXT_DEBUG,
        "text_with_debug": TEXT_DEBUG,
        "text_debug_info": TEXT_DEBUG,
        "voice": LONG_VOICE,
        "voice_only": LONG_VOICE,
        "spoken": LONG_VOICE,
        "spoken_brief": SHORT_VOICE,
        "voice_brief": SHORT_VOICE,
        "brief_voice": SHORT_VOICE,
        "voice_full": LONG_VOICE,
        "full_voice": LONG_VOICE,
        "tts": LONG_VOICE,
        "tts_brief": SHORT_VOICE,
        "voice_with_debug": VOICE_DEBUG,
        "voice_debug_info": VOICE_DEBUG,
        "text_voice": VOICE_DEBUG,
        "text_and_voice": VOICE_DEBUG,
        "voice_and_text": VOICE_DEBUG,
    }
    cleaned = aliases.get(cleaned, cleaned)
    if cleaned not in ALLOWED_RESPONSE_TYPES:
        raise ValueError(f"Unknown response type: {value}. Expected one of: {', '.join(sorted(ALLOWED_RESPONSE_TYPES))}")
    return cleaned


def response_type_options() -> list[dict[str, str]]:
    return [{"value": key, "label": label} for key, label in DISPLAY_RESPONSE_TYPES.items()]


def build_response_route(response_type: str | None, persona: str = "proto_jane") -> ResponseRoute:
    normalized = normalize_response_type(response_type)
    voice_profile_id = VOICE_PROFILE_BY_PERSONA.get(persona, "proto_jane_default")
    persona_display_name = PERSONA_DISPLAY_NAMES.get(persona, persona.replace("_", " ").title())

    if normalized == SHORT_TEXT:
        return ResponseRoute(
            response_type=normalized,
            output_channel="text",
            should_prepare_tts=False,
            tts_engine="kokoro",
            fallback_tts_engine="chatterbox",
            voice_profile_id=voice_profile_id,
            instructions=(
                "Format for short text reading. Be concise, clear, and scannable. "
                "Use only the structure needed to answer cleanly. "
                "Do not add a spoken-script preface. Preserve the active persona lens."
            ),
            persona_id=persona,
            persona_display_name=persona_display_name,
        )

    if normalized == LONG_TEXT:
        return ResponseRoute(
            response_type=normalized,
            output_channel="text",
            should_prepare_tts=False,
            tts_engine="kokoro",
            fallback_tts_engine="chatterbox",
            voice_profile_id=voice_profile_id,
            instructions=(
                "Format for full text reading. Give a complete answer with enough structure to be scannable. "
                "Do not add a spoken-script preface. Preserve the active persona lens."
            ),
            persona_id=persona,
            persona_display_name=persona_display_name,
        )

    if normalized == SHORT_VOICE:
        return ResponseRoute(
            response_type=normalized,
            output_channel="voice",
            should_prepare_tts=True,
            tts_engine="kokoro",
            fallback_tts_engine="chatterbox",
            voice_profile_id=voice_profile_id,
            instructions=(
                "Format for future spoken TTS. Keep it brief, natural, and easy to say aloud. "
                "Avoid dense lists, tables, long parentheticals, and visual-only formatting. "
                "Preserve the active persona lens."
            ),
            persona_id=persona,
            persona_display_name=persona_display_name,
        )

    if normalized == LONG_VOICE:
        return ResponseRoute(
            response_type=normalized,
            output_channel="voice",
            should_prepare_tts=True,
            tts_engine="kokoro",
            fallback_tts_engine="chatterbox",
            voice_profile_id=voice_profile_id,
            instructions=(
                "Format for future spoken TTS. Give a complete answer, but use short paragraphs "
                "and natural phrasing that Kokoro can read clearly. Preserve the active persona lens."
            ),
            persona_id=persona,
            persona_display_name=persona_display_name,
        )

    if normalized == TEXT_DEBUG:
        return ResponseRoute(
            response_type=normalized,
            output_channel="text",
            should_prepare_tts=False,
            tts_engine="kokoro",
            fallback_tts_engine="chatterbox",
            voice_profile_id=voice_profile_id,
            instructions=(
                "Format for full text reading. Include a concise debug note at the end with route, task, "
                "tool, model, or context assumptions when that information is available. "
                "Do not invent debug metadata. Preserve the active persona lens."
            ),
            persona_id=persona,
            persona_display_name=persona_display_name,
            include_debug_info=True,
        )

    return ResponseRoute(
        response_type=normalized,
        output_channel="voice",
        should_prepare_tts=True,
        tts_engine="kokoro",
        fallback_tts_engine="chatterbox",
        voice_profile_id=voice_profile_id,
        instructions=(
            "Format the main answer for future spoken TTS with natural phrasing. "
            "After the spoken-ready answer, include a short debug note for the GUI with route, task, "
            "tool, model, or context assumptions when that information is available. "
            "Do not invent debug metadata. Preserve the active persona lens."
        ),
        persona_id=persona,
        persona_display_name=persona_display_name,
        include_debug_info=True,
    )


def format_response_for_route(response_text: str, route: ResponseRoute) -> str:
    text = response_text.strip()
    if not text:
        return text

    if route.response_type == VOICE_DEBUG and not text.lower().startswith("spoken answer"):
        first_sentence = _first_sentence(text)
        return f"Spoken answer: {first_sentence}\n\nDebug detail:\n{text}"

    return text


def _first_sentence(text: str) -> str:
    for marker in [". ", "! ", "? ", "\n"]:
        index = text.find(marker)
        if index > 0:
            return text[: index + 1].strip()
    return text[:220].strip()
