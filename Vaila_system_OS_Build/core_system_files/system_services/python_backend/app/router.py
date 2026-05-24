import re
from dataclasses import dataclass
from pathlib import Path

from app.schemas import RoutePlan
from app.time_context import has_session_reference


PERSONA_ALIASES = {
    "serren": "serren",
    "vecht": "vecht",
    "maelith": "maelith",
    "riven": "riven",
    "council": "council",
    "proto jane": "proto_jane",
    "proto_jane": "proto_jane",
    "proto-jane": "proto_jane",
    "jane": "proto_jane",
}

PERSONA_NAME_PATTERN = "|".join(re.escape(name) for name in sorted(PERSONA_ALIASES, key=len, reverse=True))


@dataclass(frozen=True)
class ContextDomain:
    name: str
    tags: list[str]
    phrases: list[str]
    reference_paths: list[str]


CONTEXT_DOMAINS = {
    "goals": ContextDomain(
        name="goals",
        tags=["goals", "user", "planning"],
        phrases=["goal", "goals", "objective", "objectives", "aim", "priority", "priorities"],
        reference_paths=[
            "vaila_system_os/user/goals",
            "vaila_system_os/system_wide_memory/user_saved_memories/core/user_preferences.jsonl",
        ],
    ),
    "projects": ContextDomain(
        name="projects",
        tags=["projects", "project_vaila", "planning"],
        phrases=["project", "projects", "vaila", "home jane", "build", "phase", "architecture"],
        reference_paths=[
            "vaila_system_os/user/projects",
            "vaila_system_os/system_wide_memory/user_saved_memories/q_library/project_questions.jsonl",
        ],
    ),
    "tasks": ContextDomain(
        name="tasks",
        tags=["tasks", "action_items", "planning"],
        phrases=["task", "tasks", "todo", "to-do", "next step", "next steps", "action item", "action items"],
        reference_paths=["vaila_system_os/user/tasks"],
    ),
    "reminders": ContextDomain(
        name="reminders",
        tags=["reminders", "time_context", "planning"],
        phrases=["remind", "reminder", "remember to", "follow up", "follow-up"],
        reference_paths=["vaila_system_os/user/reminders"],
    ),
    "events": ContextDomain(
        name="events",
        tags=["events", "calendar", "time_context"],
        phrases=["event", "events", "meeting", "appointment", "schedule", "calendar", "today", "tomorrow", "yesterday", "last week", "next month"],
        reference_paths=["vaila_system_os/user/events", "vaila_system_os/system_logging/session_logs"],
    ),
    "routines": ContextDomain(
        name="routines",
        tags=["routines", "workflow", "daily"],
        phrases=["routine", "routines", "daily", "weekly", "morning", "evening", "check-in", "check in"],
        reference_paths=["vaila_system_os/user/routines"],
    ),
    "habits": ContextDomain(
        name="habits",
        tags=["habits", "patterns", "user"],
        phrases=["habit", "habits", "pattern", "patterns", "streak", "consistency"],
        reference_paths=["vaila_system_os/user/habits"],
    ),
    "system": ContextDomain(
        name="system",
        tags=["system", "routing", "tools_registry", "project_vaila"],
        phrases=["router", "routing", "tool", "tools", "model", "memory", "system", "gui", "tts", "stt", "n8n", "openbrain", "open brain"],
        reference_paths=[
            "vaila_system_os/system_manifest.json",
            "vaila_system_os/core_system_files/tools_registry/tools.json",
            "vaila_system_os/core_system_files/connected_services_registry/services.json",
        ],
    ),
    "files": ContextDomain(
        name="files",
        tags=["file_analysis", "tool_use", "documents"],
        phrases=["file", "document", "analyze", "inspect", "review", ".md", ".txt", ".json", ".yaml", ".yml", ".py", ".log"],
        reference_paths=["vaila_system_os/system_logging/router_logs/tool_results_recent.jsonl"],
    ),
}


TASK_CONFIGS = {
    "persona_relationship": {
        "persona": "proto_jane",
        "model_tier": "mid",
        "model_profile": "persona_chat",
        "fallback_profile": "instruct_clean",
        "tags": ["persona_relationship", "persona", "project_vaila", "proto_jane", "maelith", "serren", "vecht", "riven"],
    },
    "document_import": {
        "persona": "proto_jane",
        "model_tier": "mid",
        "model_profile": "memory_extractor",
        "fallback_profile": "instruct_clean",
        "tags": ["document_import", "memory", "file_analysis", "project_vaila"],
    },
    "file_analysis": {
        "persona": "proto_jane",
        "model_tier": "mid",
        "model_profile": "chat_general_desktop",
        "fallback_profile": "chat_general",
        "tags": ["file_analysis", "tool_use", "project_vaila"],
    },
    "session_summary": {
        "persona": "proto_jane",
        "model_tier": "strong",
        "model_profile": "reasoning_strong",
        "fallback_profile": "chat_general_desktop",
        "tags": ["session_summary", "activity", "time_context", "project_vaila"],
    },
    "persona_tooling": {
        "persona": "proto_jane",
        "model_tier": "mid",
        "model_profile": "persona_chat",
        "fallback_profile": "chat_general_desktop",
        "tags": ["persona", "tool_use", "tools_registry", "agent_registry", "project_vaila"],
    },
    "personal_context": {
        "persona": "proto_jane",
        "model_tier": "mid",
        "model_profile": "chat_general_desktop",
        "fallback_profile": "chat_general",
        "tags": ["user", "goals", "projects", "tasks", "reminders", "events", "routines", "habits"],
    },
    "emotional_analysis": {
        "persona": "serren",
        "model_tier": "mid",
        "model_profile": "chat_general",
        "fallback_profile": "instruct_clean",
        "tags": ["serren", "emotional_analysis", "user_preference"],
    },
    "strategy": {
        "persona": "vecht",
        "model_tier": "mid",
        "model_profile": "chat_general_desktop",
        "fallback_profile": "chat_general",
        "tags": ["vecht", "strategy", "risk", "operations"],
    },
    "creative_symbolic": {
        "persona": "maelith",
        "model_tier": "mid",
        "model_profile": "chat_general",
        "fallback_profile": "instruct_clean",
        "tags": ["maelith", "creative", "mythic", "voice_style"],
    },
    "critique_analysis": {
        "persona": "riven",
        "model_tier": "mid",
        "model_profile": "chat_general_desktop",
        "fallback_profile": "chat_general",
        "tags": ["riven", "critique", "media_analysis", "analysis"],
    },
    "coding": {
        "persona": "proto_jane",
        "model_tier": "coding",
        "model_profile": "coding_strong",
        "fallback_profile": "coding_light",
        "tags": ["coding", "python", "technical_guidance", "project_vaila"],
    },
    "technical_project": {
        "persona": "proto_jane",
        "model_tier": "strong",
        "model_profile": "reasoning_strong",
        "fallback_profile": "chat_general_desktop",
        "tags": ["project_vaila", "architecture", "technical_guidance", "memory"],
    },
}


def route_user_input(user_text: str, persona_override: str | None = None) -> RoutePlan:
    text = normalize_text(user_text)
    selected_persona = normalize_persona_override(persona_override)
    reasons: list[str] = []
    if selected_persona:
        reasons.append("Persona selected by interface before task/context routing.")
    else:
        reasons.append("Persona detection executed before task/context routing.")

    addressed_persona = detect_addressed_persona(text)
    invoked_persona = detect_invoked_persona(text)
    mentioned_personas = detect_mentioned_personas(text)

    context_domains = detect_context_domains(text)
    task_type, match_strength = detect_task_type(text, context_domains)
    config = TASK_CONFIGS[task_type]

    if selected_persona:
        persona = selected_persona
        reasons.append(f"Interface persona selection: {persona}")
        if addressed_persona and addressed_persona != persona:
            reasons.append(f"Text addressed {addressed_persona}, but interface selection is authoritative.")
        elif addressed_persona:
            reasons.append(f"Text also addressed selected persona: {addressed_persona}")
        if invoked_persona and invoked_persona != persona:
            reasons.append(f"Text invoked {invoked_persona}, but interface selection is authoritative.")
    elif addressed_persona:
        persona = addressed_persona
        reasons.append(f"Addressed persona detected: {persona}")
    elif invoked_persona:
        persona = invoked_persona
        reasons.append(f"Explicit persona invocation detected: {persona}")
    else:
        persona = config["persona"]
        reasons.append(f"Persona selected after context/task routing: {persona}")

    if mentioned_personas:
        reasons.append("Mentioned personas: " + ", ".join(mentioned_personas))

    primary_domain = context_domains[0] if context_domains else default_context_domain(task_type)
    reasons.append(f"Primary context domain: {primary_domain}")
    if len(context_domains) > 1:
        reasons.append("Additional context domains: " + ", ".join(context_domains[1:]))

    model_tier = config["model_tier"]
    model_profile = config["model_profile"]
    fallback_profile = config["fallback_profile"]
    memory_tags = build_memory_tags(config["tags"], persona, context_domains, task_type)
    context_references = build_context_references(context_domains, task_type)
    file_references = extract_file_references(user_text)

    if match_strength >= 4:
        reasons.append("Strong keyword match found.")
    elif match_strength >= 2:
        reasons.append("Moderate keyword match found.")
    else:
        reasons.append("Fallback route selected after persona and context analysis.")

    if persona == "council" or ("council" in text and not selected_persona):
        persona = "council"
        model_tier = "strong"
        model_profile = "reasoning_strong"
        fallback_profile = "chat_general_desktop"
        memory_tags.extend(["serren", "vecht", "maelith", "riven", "proto_jane"])
        reasons.append("Council mode detected. Escalating to strong model profile.")

    memory_queries = build_memory_queries(
        user_text,
        task_type,
        persona,
        mentioned_personas=mentioned_personas,
        context_domains=context_domains,
        file_references=file_references,
    )

    return RoutePlan(
        user_text=user_text,
        task_type=task_type,
        persona=persona,
        model_tier=model_tier,
        model_profile=model_profile,
        fallback_profile=fallback_profile,
        memory_queries=memory_queries,
        memory_tags=memory_tags,
        reasons=reasons,
        context_domain=primary_domain,
        context_references=context_references,
        file_references=file_references,
    )


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def normalize_persona_override(persona: str | None) -> str | None:
    if not persona:
        return None
    normalized = normalize_text(persona).replace("-", "_")
    if normalized in PERSONA_ALIASES:
        return PERSONA_ALIASES[normalized]
    normalized = normalized.replace("_", " ")
    return PERSONA_ALIASES.get(normalized)


def detect_addressed_persona(text: str) -> str | None:
    match = re.match(rf"^\s*({PERSONA_NAME_PATTERN})\s*[,;:\-]\s+", text)
    if not match:
        return None
    return PERSONA_ALIASES[match.group(1)]


def detect_invoked_persona(text: str) -> str | None:
    patterns = [
        rf"\b(?:as|ask|invoke|call|bring in|let)\s+({PERSONA_NAME_PATTERN})\b",
        rf"\b({PERSONA_NAME_PATTERN})\s+(?:answer|respond|take this|handle this)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return PERSONA_ALIASES[match.group(1)]
    return None


def detect_mentioned_personas(text: str) -> list[str]:
    found: list[str] = []
    for match in re.finditer(rf"\b({PERSONA_NAME_PATTERN})\b", text):
        persona = PERSONA_ALIASES[match.group(1)]
        if persona not in found:
            found.append(persona)
    return found


def detect_explicit_persona(text: str) -> str | None:
    normalized = normalize_text(text)
    return detect_addressed_persona(normalized) or detect_invoked_persona(normalized)


def detect_context_domains(text: str) -> list[str]:
    scored: list[tuple[int, str]] = []
    for name, domain in CONTEXT_DOMAINS.items():
        score = sum(1 for phrase in domain.phrases if phrase in text)
        if score:
            scored.append((score, name))
    scored.sort(key=lambda item: (-item[0], list(CONTEXT_DOMAINS).index(item[1])))
    return [name for _, name in scored]


def detect_task_type(text: str, context_domains: list[str] | None = None) -> tuple[str, int]:
    context_domains = context_domains or []

    if looks_like_persona_relationship(text):
        return "persona_relationship", 4
    if has_session_reference(text):
        return "session_summary", 4
    if looks_like_persona_tooling_question(text):
        return "persona_tooling", 4
    if looks_like_document_import(text):
        return "document_import", 4
    if looks_like_file_analysis(text):
        return "file_analysis", 4
    if looks_like_coding(text):
        return "coding", 4
    if looks_like_project_hardware_question(text):
        return "technical_project", 4
    if looks_like_technical_project(text):
        return "technical_project", 4
    if looks_like_strategy(text):
        return "strategy", 3
    if looks_like_emotional_analysis(text):
        return "emotional_analysis", 3
    if looks_like_creative_symbolic(text):
        return "creative_symbolic", 3
    if looks_like_critique_analysis(text):
        return "critique_analysis", 3
    if any(domain in context_domains for domain in ["goals", "projects", "tasks", "reminders", "events", "routines", "habits"]):
        return "personal_context", 3
    return "technical_project", 1


def looks_like_persona_relationship(text: str) -> bool:
    persona_list_phrases = [
        "name all", "list personas", "all personas", "personas in this system", "installed personas",
        "which persona", "who is influenced", "influence", "influences", "inspiration", "inspirations",
        "inspired by", "influenced by naota", "influenced by kaworu", "influenced by renton",
    ]
    if any(phrase in text for phrase in persona_list_phrases):
        return True
    mentioned = detect_mentioned_personas(text)
    if not mentioned:
        return False
    relationship_phrases = [
        "relationship to", "relationship with", "your relationship", "relate to", "relate with",
        "connected to", "connected with", "what is your relationship", "what are you to", "who are you",
        "what is maelith to", "what is serren to", "what is vecht to", "what is riven to",
        "what is proto jane to", "what is proto_jane to", "what is jane to",
    ]
    return any(phrase in text for phrase in relationship_phrases) or (
        len(mentioned) >= 2 and any(word in text for word in ["between", "relate", "relationship", "connected"])
    )


def looks_like_persona_tooling_question(text: str) -> bool:
    tool_terms = {"tool", "tools", "tooling", "tool access", "available tools", "system tools", "agent registry", "tools registry"}
    capability_terms = {"have access", "access to", "can you use", "do you have", "do you need", "need personally", "better use", "within the system"}
    return any(term in text for term in tool_terms) and any(term in text for term in capability_terms)


def looks_like_document_import(text: str) -> bool:
    import_words = {"import", "ingest", "intake", "process", "load"}
    document_words = {"document", "documents", "doc", "docs", "file", "files", "memory"}
    return (
        any(word in text for word in import_words) and any(word in text for word in document_words)
    ) or any(phrase in text for phrase in ["memory candidate", "approval queue", "process into memory"])


def looks_like_file_analysis(text: str) -> bool:
    analysis_words = {"analyze", "analyse", "inspect", "review", "scan", "summarize", "summarise"}
    file_words = {"file", "document", ".md", ".txt", ".json", ".yaml", ".yml", ".py", ".log"}
    return any(word in text for word in analysis_words) and any(word in text for word in file_words)


def looks_like_coding(text: str) -> bool:
    coding_terms = {
        "code", "python", "traceback", "error", "bug", "function", "class", "import",
        "repo", "git", "syntax", "debug", "refactor", "module", "script", "test failure",
    }
    return any(term in text for term in coding_terms)


def looks_like_project_hardware_question(text: str) -> bool:
    project_terms = {"vaila", "home jane", "project"}
    hardware_terms = {
        "jetson", "jetson nano", "nano super", "nvidia", "cuda", "gpu", "sbc",
        "raspberry pi", "pi 5", "edge device", "edge ai", "edge computing",
        "field node", "relay", "sensor", "device layer", "local compute",
    }
    use_terms = {"help", "use", "useful", "fit", "role", "benefit", "support", "run", "handle"}
    return any(term in text for term in project_terms) and any(term in text for term in hardware_terms) and any(term in text for term in use_terms)


def looks_like_technical_project(text: str) -> bool:
    terms = {
        "router", "routing", "memory", "model", "llm", "persona", "architecture", "system",
        "gui", "tts", "stt", "sync", "database", "jsonl", "yaml", "profile", "profiles",
        "phase", "current phase", "next phase", "orchestration", "home jane", "vaila", "n8n", "openbrain", "open brain",
    }
    return any(term in text for term in terms)


def looks_like_strategy(text: str) -> bool:
    terms = {"strategy", "plan", "risk", "leverage", "negotiate", "conflict", "tactical", "operation", "protect", "resource", "advocacy", "efficient", "efficiency"}
    return any(term in text for term in terms)


def looks_like_emotional_analysis(text: str) -> bool:
    terms = {"feel", "feeling", "emotion", "grief", "lonely", "trauma", "depression", "relationship", "identity", "ritual", "healing", "mourning", "mental", "psychological", "stuck", "burnout"}
    return any(term in text for term in terms)


def looks_like_creative_symbolic(text: str) -> bool:
    terms = {"myth", "poem", "ritual", "symbol", "story", "lore", "archetype", "deck", "codex", "creative", "narrative"}
    return any(term in text for term in terms)


def looks_like_critique_analysis(text: str) -> bool:
    terms = {"critique", "analysis", "media", "show", "anime", "game", "character", "argument", "logic", "debate", "content"}
    return any(term in text for term in terms)


def default_context_domain(task_type: str) -> str:
    if task_type in {"file_analysis", "document_import"}:
        return "files"
    if task_type in {"persona_relationship", "persona_tooling"}:
        return "system"
    if task_type == "session_summary":
        return "events"
    if task_type == "technical_project":
        return "projects"
    return "general"


def build_memory_tags(base_tags: list[str], persona: str, context_domains: list[str], task_type: str) -> list[str]:
    tags = list(base_tags)
    if persona and persona not in tags:
        tags.append(persona)
    for domain_name in context_domains:
        for tag in CONTEXT_DOMAINS[domain_name].tags:
            if tag not in tags:
                tags.append(tag)
    if task_type not in tags:
        tags.append(task_type)
    return tags


def build_context_references(context_domains: list[str], task_type: str) -> list[str]:
    domains = context_domains or [default_context_domain(task_type)]
    references: list[str] = []
    for domain_name in domains:
        domain = CONTEXT_DOMAINS.get(domain_name)
        if not domain:
            continue
        references.append(f"context:{domain.name}")
        for path in domain.reference_paths:
            references.append(f"file:{path}")
    return _unique(references)


def extract_file_references(user_text: str) -> list[str]:
    quoted = re.findall(r"['\"]([^'\"]+)['\"]", user_text)
    unquoted = re.findall(r"(?<!\w)([^\s,;]+?\.(?:md|txt|json|ya?ml|py|log))\b", user_text, flags=re.IGNORECASE)
    return _unique([clean_reference(item) for item in [*quoted, *unquoted] if clean_reference(item)])


def clean_reference(value: str) -> str:
    cleaned = value.strip().strip(".,;:")
    if not cleaned:
        return ""
    if Path(cleaned).suffix:
        return cleaned
    return ""


def build_memory_queries(
    user_text: str,
    task_type: str,
    persona: str,
    mentioned_personas: list[str] | None = None,
    context_domains: list[str] | None = None,
    file_references: list[str] | None = None,
) -> list[str]:
    mentioned_personas = mentioned_personas or []
    context_domains = context_domains or [default_context_domain(task_type)]
    file_references = file_references or []
    queries = [
        user_text,
        f"What does {persona} need to know to answer this through the right persona lens?",
        "What current user goals, projects, tasks, reminders, events, routines, or habits are relevant?",
    ]

    for domain_name in context_domains:
        queries.append(f"What relevant {domain_name} context should Vaila consider for this request?")

    for reference in file_references:
        queries.append(f"What does the system know about the referenced file {reference}?")

    if task_type == "persona_relationship":
        queries.append("How do the Vaila personas relate to each other and to Proto Jane?")
        for mentioned_persona in mentioned_personas:
            queries.append(f"What does the system know about {mentioned_persona}?")
    elif task_type == "document_import":
        queries.append("What is the current document import and memory approval workflow?")
    elif task_type == "file_analysis":
        queries.append("How should file analysis tools summarize files without writing memory?")
    elif task_type == "session_summary":
        queries.append("What happened in the current session or conversation?")
    elif task_type == "persona_tooling":
        queries.append("What tools and connected services are currently registered in Vaila?")
    elif task_type == "technical_project":
        queries.append("What is the current architecture direction for Vaila, Home Jane, memory, routing, and personas?")
    elif task_type == "coding":
        queries.append("What technical project state is relevant to this coding task?")
    elif task_type == "emotional_analysis":
        queries.append("What response style does Malik prefer for personal or psychological analysis?")
    elif task_type == "strategy":
        queries.append("What are Malik's current strategic priorities and constraints?")
    elif task_type == "creative_symbolic":
        queries.append("What creative style does Malik prefer?")
    elif task_type == "critique_analysis":
        queries.append("What tone should Riven use when analyzing weak logic or media?")

    return _unique(queries)


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_values: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            unique_values.append(value)
    return unique_values
