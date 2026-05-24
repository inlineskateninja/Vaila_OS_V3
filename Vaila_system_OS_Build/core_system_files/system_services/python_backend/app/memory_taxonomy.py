from __future__ import annotations

import re

BASE_MEMORY_CATEGORIES = {
    "projects": ["project", "vaila", "home jane", "phase", "repo", "architecture", "build"],
    "goals": ["goal", "want to", "aim", "target", "objective", "priority"],
    "tasks": ["task", "todo", "next action", "fix", "build", "test", "update", "implement"],
    "reminders": ["remind", "reminder", "later", "tomorrow", "schedule", "remember to"],
    "personas": ["persona", "serren", "maelith", "vecht", "riven", "proto jane", "council"],
    "models": ["model", "lm studio", "qwen", "gemma", "fallback", "profile"],
    "system": ["router", "memory", "candidate", "service", "api", "gui", "desktop", "context"],
}

CATEGORY_DEFAULT_PATHS = {
    "projects": "projects/approved_projects.jsonl",
    "goals": "goals/approved_goals.jsonl",
    "tasks": "tasks/approved_tasks.jsonl",
    "reminders": "reminders/approved_reminders.jsonl",
    "personas": "personas/approved_personas.jsonl",
    "models": "models/approved_models.jsonl",
    "system": "system/approved_system.jsonl",
    "general": "imported/approved_imports.jsonl",
}


def normalize_category(category: str | None) -> str:
    if not category:
        return "general"
    clean = re.sub(r"[^a-z0-9_\-]+", "_", category.lower()).strip("_")
    return clean or "general"


def categorize_memory(question: str = "", answer: str = "", tags: list[str] | None = None) -> str:
    tags = tags or []
    combined = f"{question} {answer} {' '.join(tags)}".lower()

    for tag in tags:
        clean_tag = normalize_category(tag)
        if clean_tag in CATEGORY_DEFAULT_PATHS and clean_tag != "general":
            return clean_tag

    scores: dict[str, int] = {}
    for category, words in BASE_MEMORY_CATEGORIES.items():
        score = 0
        for word in words:
            if word in combined:
                score += 1
        if score:
            scores[category] = score

    if not scores:
        return "general"

    return sorted(scores.items(), key=lambda item: item[1], reverse=True)[0][0]


def path_for_category(category: str | None) -> str:
    clean = normalize_category(category)
    return CATEGORY_DEFAULT_PATHS.get(clean, CATEGORY_DEFAULT_PATHS["general"])
