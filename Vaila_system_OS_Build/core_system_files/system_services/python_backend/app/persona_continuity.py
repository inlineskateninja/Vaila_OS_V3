from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


PERSONA_DISPLAY_NAMES = {
    "proto_jane": "Proto Jane",
    "serren": "Serren",
    "vecht": "Vecht",
    "maelith": "Maelith",
    "riven": "Riven",
    "council": "Council",
}

PERSONA_LENS_SUMMARIES = {
    "proto_jane": "system continuity, coordination, memory, and practical assistant behavior",
    "serren": "grounded emotional context, attentiveness, steadiness, and human meaning",
    "vecht": "strategy, risk, boundaries, resources, and practical protection",
    "maelith": "symbolic meaning, creative structure, atmosphere, and mythic interpretation",
    "riven": "critique, logic, media analysis, and clear-eyed testing of weak reasoning",
    "council": "structured multi-perspective review without overriding Malik",
}


@dataclass
class PersonaContinuity:
    active_persona: str
    display_name: str
    lens_summary: str
    source: str = "route_plan"
    must_preserve: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_prompt_block(self) -> str:
        return "\n".join(
            [
                "[Persona Continuity]",
                f"Active persona: {self.display_name} ({self.active_persona})",
                f"Lens: {self.lens_summary}",
                f"Source: {self.source}",
                "Continuity rule: preserve this active persona through model fallback, tool dispatch, response formatting, and final answer.",
                "If a system limitation must be explained, explain it through this persona lens instead of dropping into generic assistant voice.",
                "Do not switch to another persona unless the user explicitly asks for that switch or council mode is active.",
            ]
        )


def build_persona_continuity(persona: str, source: str = "route_plan") -> PersonaContinuity:
    persona_id = persona or "proto_jane"
    return PersonaContinuity(
        active_persona=persona_id,
        display_name=PERSONA_DISPLAY_NAMES.get(persona_id, persona_id.replace("_", " ").title()),
        lens_summary=PERSONA_LENS_SUMMARIES.get(persona_id, "the selected Vaila persona lens"),
        source=source,
    )
