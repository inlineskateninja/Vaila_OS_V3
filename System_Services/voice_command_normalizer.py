from __future__ import annotations

import re
from typing import Any


WAKE_PREFIXES: dict[str, str] = {
    "vaila": "proto_jane",
    "proto jane": "proto_jane",
    "jane": "proto_jane",
    "serren": "serren",
    "vecht": "vecht",
    "maelith": "maelith",
    "riven": "riven",
}

COMMON_STT_REPAIRS: list[tuple[str, str]] = [
    (r"\bvilla\b", "vaila"),
    (r"\bvela\b", "vaila"),
    (r"\bvala\b", "vaila"),
    (r"\bproto chain\b", "proto jane"),
    (r"\bproto jain\b", "proto jane"),
    (r"\bseren\b", "serren"),
    (r"\bcertain\b", "serren"),
    (r"\bvekt\b", "vecht"),
    (r"\bvector\b", "vecht"),
    (r"\bmalice\b", "maelith"),
    (r"\bmailith\b", "maelith"),
    (r"\bribbon\b", "riven"),
]

VOICE_COMMAND_REWRITES: list[tuple[str, str]] = [
    (r"\bput this on my calendar\b", "schedule this calendar event"),
    (r"\bmake a task\b", "add a task"),
    (r"\bsend an email\b", "draft an email"),
    (r"\bsend a email\b", "draft an email"),
    (r"\bwrite this down\b", "take a note"),
    (r"\bremind me\b", "remind me"),
    (r"\blook up\b", "look up"),
    (r"\bfind the file\b", "find the file"),
]


def repair_common_stt_errors(transcript: str) -> str:
    repaired = transcript.strip()
    for pattern, replacement in COMMON_STT_REPAIRS:
        repaired = re.sub(pattern, replacement, repaired, flags=re.IGNORECASE)
    return _collapse_spaces(repaired)


def detect_wake_prefix(transcript: str) -> dict[str, Any]:
    text = _plain_normalize(transcript)
    for wake_word, persona_hint in WAKE_PREFIXES.items():
        pattern = rf"^\s*{re.escape(wake_word)}\b[\s,.:;-]*"
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return {
                "wake_word_detected": True,
                "wake_word": wake_word,
                "persona_hint": persona_hint,
                "matched_text": match.group(0).strip(),
            }

    return {
        "wake_word_detected": False,
        "wake_word": "",
        "persona_hint": "",
        "matched_text": "",
    }


def strip_wake_prefix(transcript: str) -> str:
    wake = detect_wake_prefix(transcript)
    text = _plain_normalize(transcript)
    if not wake["wake_word_detected"]:
        return text

    stripped = re.sub(
        rf"^\s*{re.escape(wake['wake_word'])}\b[\s,.:;-]*",
        "",
        text,
        count=1,
        flags=re.IGNORECASE,
    )
    return _collapse_spaces(stripped)


def normalize_spoken_dates_times(transcript: str) -> str:
    text = transcript
    replacements = [
        (r"\btwo p m\b", "2 pm"),
        (r"\btwo pm\b", "2 pm"),
        (r"\bthree p m\b", "3 pm"),
        (r"\bthree pm\b", "3 pm"),
        (r"\bfour p m\b", "4 pm"),
        (r"\bfour pm\b", "4 pm"),
        (r"\bfive p m\b", "5 pm"),
        (r"\bfive pm\b", "5 pm"),
        (r"\bsix p m\b", "6 pm"),
        (r"\bsix pm\b", "6 pm"),
        (r"\bseven p m\b", "7 pm"),
        (r"\bseven pm\b", "7 pm"),
        (r"\beight p m\b", "8 pm"),
        (r"\beight pm\b", "8 pm"),
        (r"\bnine p m\b", "9 pm"),
        (r"\bnine pm\b", "9 pm"),
        (r"\bten p m\b", "10 pm"),
        (r"\bten pm\b", "10 pm"),
        (r"\beleven p m\b", "11 pm"),
        (r"\beleven pm\b", "11 pm"),
        (r"\btwelve p m\b", "12 pm"),
        (r"\btwelve pm\b", "12 pm"),
        (r"\bone p m\b", "1 pm"),
        (r"\bone pm\b", "1 pm"),
        (r"\btwo a m\b", "2 am"),
        (r"\btwo am\b", "2 am"),
        (r"\bthree a m\b", "3 am"),
        (r"\bthree am\b", "3 am"),
        (r"\bfour a m\b", "4 am"),
        (r"\bfour am\b", "4 am"),
        (r"\bfive a m\b", "5 am"),
        (r"\bfive am\b", "5 am"),
        (r"\bsix a m\b", "6 am"),
        (r"\bsix am\b", "6 am"),
        (r"\bseven a m\b", "7 am"),
        (r"\bseven am\b", "7 am"),
        (r"\beight a m\b", "8 am"),
        (r"\beight am\b", "8 am"),
        (r"\bnine a m\b", "9 am"),
        (r"\bnine am\b", "9 am"),
        (r"\bten a m\b", "10 am"),
        (r"\bten am\b", "10 am"),
        (r"\beleven a m\b", "11 am"),
        (r"\beleven am\b", "11 am"),
        (r"\btwelve a m\b", "12 am"),
        (r"\btwelve am\b", "12 am"),
        (r"\bone a m\b", "1 am"),
        (r"\bone am\b", "1 am"),
    ]

    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return _collapse_spaces(text)


def normalize_voice_transcript(transcript: str) -> dict[str, Any]:
    confidence_notes: list[str] = []
    repaired = repair_common_stt_errors(transcript)
    if repaired != transcript.strip():
        confidence_notes.append("common_stt_repairs_applied")

    wake = detect_wake_prefix(repaired)
    command_text = strip_wake_prefix(repaired)
    if wake["wake_word_detected"]:
        confidence_notes.append(f"wake_prefix:{wake['wake_word']}")

    normalized = _plain_normalize(command_text)
    normalized = normalize_spoken_dates_times(normalized)
    normalized = _rewrite_voice_phrases(normalized, confidence_notes)

    return {
        "raw_transcript": transcript,
        "normalized_text": normalized,
        "wake_word_detected": wake["wake_word_detected"],
        "persona_hint": wake["persona_hint"] or "proto_jane",
        "confidence_notes": confidence_notes,
    }


def _rewrite_voice_phrases(text: str, confidence_notes: list[str]) -> str:
    rewritten = text
    for pattern, replacement in VOICE_COMMAND_REWRITES:
        updated = re.sub(pattern, replacement, rewritten, flags=re.IGNORECASE)
        if updated != rewritten:
            confidence_notes.append(f"voice_phrase_rewrite:{replacement}")
        rewritten = updated
    return _collapse_spaces(rewritten)


def _plain_normalize(text: str) -> str:
    lowered = text.lower().strip()
    lowered = re.sub(r"[^\w\s:%$./@+-]", " ", lowered)
    return _collapse_spaces(lowered)


def _collapse_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
