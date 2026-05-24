from __future__ import annotations

from app.persona_continuity import PERSONA_DISPLAY_NAMES
from app.schemas import RoutePlan


def persona_selection_notice(route_plan: RoutePlan) -> str:
    """Return the user-visible correction when typed persona and selected persona differ."""
    mismatched_personas: list[str] = []
    for reason in route_plan.reasons:
        if "but interface selection is authoritative" not in reason:
            continue
        if reason.startswith("Text addressed "):
            persona = reason.removeprefix("Text addressed ").split(",", 1)[0].strip()
        elif reason.startswith("Text invoked "):
            persona = reason.removeprefix("Text invoked ").split(",", 1)[0].strip()
        else:
            continue
        if persona and persona not in mismatched_personas:
            mismatched_personas.append(persona)

    if not mismatched_personas:
        return ""

    active_name = PERSONA_DISPLAY_NAMES.get(route_plan.persona, route_plan.persona.replace("_", " ").title())
    target_names = [
        PERSONA_DISPLAY_NAMES.get(persona, persona.replace("_", " ").title())
        for persona in mismatched_personas
    ]
    target_text = ", ".join(target_names)
    return (
        f"Note: {active_name} is the selected persona right now, "
        f"so I will answer from {active_name}'s lens rather than {target_text}."
    )


def persona_selection_prompt_block(route_plan: RoutePlan) -> str:
    notice = persona_selection_notice(route_plan)
    if not notice:
        return "[Persona Selection]\nNo interface/persona mismatch detected."
    return (
        "[Persona Selection]\n"
        "The interface-selected persona is authoritative for this text chat request.\n"
        f"Required user-visible correction: {notice}"
    )
