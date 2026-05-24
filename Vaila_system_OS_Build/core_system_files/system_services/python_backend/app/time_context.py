from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_TIMEZONE = "America/New_York"


@dataclass
class TimeReference:
    phrase: str
    start_date: str
    end_date: str
    meaning: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TimeContext:
    request_utc: str
    request_local: str
    timezone: str
    local_date: str
    weekday: str
    references: list[TimeReference] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_utc": self.request_utc,
            "request_local": self.request_local,
            "timezone": self.timezone,
            "local_date": self.local_date,
            "weekday": self.weekday,
            "references": [reference.to_dict() for reference in self.references],
        }

    def to_prompt_block(self) -> str:
        lines = [
            "[Time Context]",
            f"Request UTC: {self.request_utc}",
            f"Request local: {self.request_local}",
            f"Timezone: {self.timezone}",
            f"Local date: {self.local_date} ({self.weekday})",
        ]
        if self.references:
            lines.append("Resolved relative references:")
            for reference in self.references:
                lines.append(
                    f"- {reference.phrase}: {reference.start_date} to {reference.end_date} ({reference.meaning})"
                )
        else:
            lines.append("Resolved relative references: none detected")
        return "\n".join(lines)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def build_time_context(user_text: str, timezone_name: str = DEFAULT_TIMEZONE, now: datetime | None = None) -> TimeContext:
    tz = resolve_timezone(timezone_name, now=now)
    current_utc = now.astimezone(timezone.utc) if now else datetime.now(timezone.utc)
    current_local = current_utc.astimezone(tz)
    references = detect_time_references(user_text, current_local)
    return TimeContext(
        request_utc=current_utc.isoformat(timespec="seconds"),
        request_local=current_local.isoformat(timespec="seconds"),
        timezone=timezone_name,
        local_date=current_local.date().isoformat(),
        weekday=current_local.strftime("%A"),
        references=references,
    )


def resolve_timezone(timezone_name: str, now: datetime | None = None):
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        if timezone_name == DEFAULT_TIMEZONE:
            current_utc = now.astimezone(timezone.utc) if now else datetime.now(timezone.utc)
            return timezone(eastern_utc_offset(current_utc), name=DEFAULT_TIMEZONE)
        return datetime.now().astimezone().tzinfo or timezone.utc


def eastern_utc_offset(current_utc: datetime) -> timedelta:
    year = current_utc.year
    dst_start = _nth_weekday_of_month(year, 3, 6, 2).replace(hour=7, tzinfo=timezone.utc)
    dst_end = _nth_weekday_of_month(year, 11, 6, 1).replace(hour=6, tzinfo=timezone.utc)
    if dst_start <= current_utc < dst_end:
        return timedelta(hours=-4)
    return timedelta(hours=-5)


def _nth_weekday_of_month(year: int, month: int, weekday: int, occurrence: int) -> datetime:
    current = datetime(year, month, 1)
    days_until_weekday = (weekday - current.weekday()) % 7
    day = 1 + days_until_weekday + (occurrence - 1) * 7
    return datetime(year, month, day)


def detect_time_references(user_text: str, current_local: datetime) -> list[TimeReference]:
    text = re.sub(r"\s+", " ", user_text.lower()).strip()
    today = current_local.date()
    references: list[TimeReference] = []

    def add(phrase: str, start, end, meaning: str) -> None:
        if phrase in text and not any(reference.phrase == phrase for reference in references):
            references.append(TimeReference(phrase, start.isoformat(), end.isoformat(), meaning))

    add("today", today, today, "current local calendar day")
    add("yesterday", today - timedelta(days=1), today - timedelta(days=1), "previous local calendar day")
    add("tomorrow", today + timedelta(days=1), today + timedelta(days=1), "next local calendar day")

    week_start = today - timedelta(days=today.weekday())
    add("this week", week_start, week_start + timedelta(days=6), "current Monday-Sunday local week")
    add("last week", week_start - timedelta(days=7), week_start - timedelta(days=1), "previous Monday-Sunday local week")
    add("next week", week_start + timedelta(days=7), week_start + timedelta(days=13), "next Monday-Sunday local week")

    month_start = today.replace(day=1)
    next_month_start = _add_months(month_start, 1)
    last_month_start = _add_months(month_start, -1)
    add("this month", month_start, next_month_start - timedelta(days=1), "current local calendar month")
    add("last month", last_month_start, month_start - timedelta(days=1), "previous local calendar month")
    add("next month", next_month_start, _add_months(month_start, 2) - timedelta(days=1), "next local calendar month")

    for phrase in ["this conversation", "this chat", "this session", "current session", "our conversation"]:
        if phrase in text and not any(reference.phrase == phrase for reference in references):
            references.append(TimeReference(phrase, today.isoformat(), today.isoformat(), "current loaded activity/session context"))

    return references


def has_session_reference(user_text: str) -> bool:
    text = re.sub(r"\s+", " ", user_text.lower()).strip()
    return any(
        phrase in text
        for phrase in [
            "this session",
            "current session",
            "this conversation",
            "our conversation",
            "this chat",
            "summarize session",
            "summarize this session",
            "recap this session",
        ]
    )


def _add_months(value, months: int):
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    return value.replace(year=year, month=month, day=1)
