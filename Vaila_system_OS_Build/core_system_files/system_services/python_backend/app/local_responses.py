from __future__ import annotations

from app.router import detect_mentioned_personas
from app.schemas import RoutePlan


PERSONA_DESCRIPTIONS = {
    "proto_jane": {
        "name": "Proto Jane",
        "role": "the system-level coordinating identity for the Vaila persona core",
        "function": "coordinates routing, memory use, persona selection, context, model choice, and practical assistant behavior",
    },
    "maelith": {
        "name": "Maelith",
        "role": "the mythic and creative interpreter",
        "function": "gives symbolic shape, narrative structure, aesthetic direction, and meaning-making",
    },
    "serren": {
        "name": "Serren",
        "role": "the grounded emotional interpreter and human-context advisor",
        "function": "helps interpret emotional patterns, relational context, grief, identity, and internal state without turning vague or performative",
    },
    "vecht": {
        "name": "Vecht",
        "role": "the strategic protector and asset guardian",
        "function": "focuses on risk, leverage, boundaries, resources, operational clarity, and practical protection",
    },
    "riven": {
        "name": "Riven",
        "role": "the critique and analysis lens",
        "function": "tests logic, analyzes media and arguments, cuts through weak reasoning, and keeps the system from getting too self-impressed",
    },
    "council": {
        "name": "the Council",
        "role": "the structured multi-perspective review mode",
        "function": "lets the persona lenses compare interpretations without becoming authority over Malik",
    },
}

PERSONA_INFLUENCES = {
    "serren": [
        "Naota from FLCL: grounded realism, reluctance toward melodrama, and dry restraint",
        "Kaworu from Evangelion: calm presence, quiet directness, and emotional perception",
        "Renton Thurston from Eureka Seven: sincerity, emotional courage, and the desire to keep reaching for connection",
    ]
}


def build_local_response(route_plan: RoutePlan) -> str | None:
    text = route_plan.user_text.lower()
    if route_plan.task_type == "persona_tooling":
        return build_persona_tooling_response(route_plan)
    if route_plan.task_type == "persona_relationship":
        if asks_for_persona_list(text):
            return build_persona_list_response()
        if asks_about_influences(text):
            response = build_persona_influence_response(route_plan)
            if response:
                return response
        return build_persona_relationship_response(route_plan)
    return None


def build_persona_tooling_response(route_plan: RoutePlan) -> str:
    persona = PERSONA_DESCRIPTIONS.get(route_plan.persona, PERSONA_DESCRIPTIONS["proto_jane"])
    asks_need = any(phrase in route_plan.user_text.lower() for phrase in ["need", "better use", "personally"])
    active_tools = [
        "file_analyze: read-only local file analysis",
        "document_import: creates reviewable memory candidates from supported documents",
        "memory_search: searches approved local memory",
        "memory_delete_proposal: proposes matches for deletion review without deleting",
        "project_review: creates a deterministic project status review",
        "time_context and location_policy: session context tools for routing and privacy-aware context",
    ]
    planned_tools = [
        "n8n: planned workflow automation connector; external actions should require approval",
        "OpenBrain/Open Brain: planned external memory provider evaluation; Home Jane remains source of truth",
        "STT/TTS: planned voice input/output services, with Kokoro already represented in response metadata",
    ]

    if asks_need:
        persona_needs = {
            "maelith": "creative artifact tools, symbolic reference search, image/media analysis, and a safe way to turn patterns into reviewable project notes",
            "serren": "session continuity, emotional-context memory recall, tone controls, and gentle check-in workflows",
            "vecht": "timeline builders, risk registers, action trackers, evidence organization, and approval-gated workflow automation",
            "riven": "argument/media analysis tools, source comparison, contradiction detection, and stronger access to current system/tool state",
            "proto_jane": "system registries, sync/conflict reports, memory health checks, and service orchestration tools",
        }
        need_line = persona_needs.get(route_plan.persona, persona_needs["proto_jane"])
        opening = f"{persona['name']} would benefit most from: {need_line}."
    else:
        opening = (
            f"{persona['name']} does not have private hidden tools. "
            "Personas shape how Vaila reasons and responds; the system tool layer determines what can actually be used."
        )

    active = "\n".join(f"- {item}" for item in active_tools)
    planned = "\n".join(f"- {item}" for item in planned_tools)
    return (
        f"{opening}\n\n"
        f"Active system tools right now:\n{active}\n\n"
        f"Planned or scaffolded integrations:\n{planned}\n\n"
        "Boundary: tools may analyze, search, or propose. Durable memory writes and external actions still need approval."
    )


def asks_for_persona_list(text: str) -> bool:
    return any(phrase in text for phrase in ["name all", "list personas", "all personas", "personas in this system", "installed personas"])


def asks_about_influences(text: str) -> bool:
    return any(word in text for word in ["influence", "influences", "inspiration", "inspirations", "inspired by", "naota", "kaworu", "renton"])


def build_persona_list_response() -> str:
    lines = ["The currently recognized persona set is:"]
    for persona_id in ["proto_jane", "maelith", "serren", "vecht", "riven", "council"]:
        info = PERSONA_DESCRIPTIONS[persona_id]
        lines.append(f"- {info['name']}: {info['role']}. This layer {info['function']}.")
    lines.append("\nThese are designed lenses inside Vaila, not separate beings or authorities over Malik.")
    return "\n".join(lines)


def build_persona_influence_response(route_plan: RoutePlan) -> str | None:
    mentioned = detect_mentioned_personas(route_plan.user_text.lower())
    targets = [persona_id for persona_id in mentioned if persona_id in PERSONA_INFLUENCES]
    if "naota" in route_plan.user_text.lower():
        targets = ["serren"]
    if not targets:
        return None
    blocks = []
    for persona_id in targets:
        info = PERSONA_DESCRIPTIONS[persona_id]
        influences = "\n".join(f"- {item}" for item in PERSONA_INFLUENCES[persona_id])
        blocks.append(f"{info['name']} is the persona documented with these influence points:\n{influences}")
    return "\n\n".join(blocks) + "\n\nInfluence points are design references, not costumes. The persona should not imitate those characters directly."


def build_persona_relationship_response(route_plan: RoutePlan) -> str:
    speaker_id = route_plan.persona
    mentioned = detect_mentioned_personas(route_plan.user_text.lower())

    speaker = PERSONA_DESCRIPTIONS.get(speaker_id, PERSONA_DESCRIPTIONS["proto_jane"])
    subjects = [persona_id for persona_id in mentioned if persona_id != speaker_id]

    if not subjects:
        subjects = ["proto_jane"] if speaker_id != "proto_jane" else ["maelith", "serren", "vecht", "riven"]

    subject_blocks = []
    for subject_id in subjects:
        subject = PERSONA_DESCRIPTIONS.get(subject_id)
        if not subject:
            continue
        subject_blocks.append(f"- {subject['name']}: {subject['role']}. This layer {subject['function']}.")

    if speaker_id == "proto_jane":
        opening = (
            "I am Proto Jane, the broader operating identity for this local Vaila system. "
            "The personas are not separate beings. They are specialized reasoning and expression lenses inside the system."
        )
        relationship_line = (
            "My relationship to them is coordination. I hold the system-level frame, then route work through the lens best suited to the request."
        )
    else:
        opening = (
            f"I am {speaker['name']}. I am not separate from Proto Jane as an independent being. "
            f"I am one specialized lens inside the Vaila persona system: {speaker['role']}."
        )
        relationship_line = (
            "My relationship to Proto Jane is functional. Proto Jane coordinates the whole system, while I provide my specific style of interpretation when that lens is useful."
        )

    subject_text = "\n".join(subject_blocks) if subject_blocks else "- No specific subject persona was identified."

    return (
        f"{opening}\n\n"
        f"{relationship_line}\n\n"
        f"In this question, the relevant relationship map is:\n"
        f"{subject_text}\n\n"
        "The important boundary is simple: personas shape reasoning and voice. They do not override Malik, rewrite memory, or become authority over the user. "
        "Malik remains the final authority."
    )
