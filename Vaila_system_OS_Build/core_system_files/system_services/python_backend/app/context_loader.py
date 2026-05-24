from __future__ import annotations

from pathlib import Path

from app.persona_library import PersonaLibrary
from app.schemas import RoutePlan

FOUNDATION_FILES = [
    "Project Vaila Build Philosophy.txt",
    "Project_Vaila_Build_Philosophy.txt",
    "Vaila System Core - Software Architecture Principle.txt",
    "Software_Architecture_Principle.txt",
]

MAX_FOUNDATION_CHARS_PER_FILE = 1600
MAX_PERSONA_CHARS_PER_FILE = 1200


class ContextLoader:
    def __init__(self, project_root: str | Path, persona_library: PersonaLibrary, foundation_root: str | Path | None = None):
        self.project_root = Path(project_root)
        self.persona_library = persona_library
        self.personas_root = self.persona_library.personas_root
        self.foundation_root = Path(foundation_root) if foundation_root else self.project_root

    def build_context_blocks(self, route_plan: RoutePlan) -> dict[str, str]:
        return {
            "foundation_context": self.load_foundation_context(),
            "persona_context": self.load_persona_context(route_plan),
            "task_instructions": self.build_task_instructions(route_plan),
        }

    def load_foundation_context(self) -> str:
        blocks = []
        seen = set()
        for filename in FOUNDATION_FILES:
            path = self.foundation_root / filename
            if not path.exists() and self.foundation_root != self.project_root:
                path = self.project_root / filename
            if not path.exists() or path in seen:
                continue
            seen.add(path)
            blocks.append(f"[Foundation: {path.name}]\n{self._read(path)[:MAX_FOUNDATION_CHARS_PER_FILE]}")
        return "\n\n".join(blocks) if blocks else "[Foundation Context]\nNo foundation files found."

    def load_persona_context(self, route_plan: RoutePlan) -> str:
        persona_ids = self._persona_ids(route_plan)
        blocks = [self.persona_library.to_context_block()]
        for persona_id in persona_ids:
            info = self.persona_library.get(persona_id)
            if info:
                blocks.append(
                    f"[Active/Relevant Persona: {info.display_name}]\n"
                    f"ID: {info.persona_id}\nRole: {info.role}\nPronouns: {info.pronouns}\n"
                    f"Influences: {'; '.join(info.influences) if info.influences else 'none documented'}"
                )
            persona_dir = self.personas_root / persona_id
            if persona_dir.exists():
                for filename in ["manifest.yaml", "voice_style.md", "boundaries.md"]:
                    path = persona_dir / filename
                    if path.exists():
                        blocks.append(f"[Persona File: {persona_id}/{filename}]\n{self._read(path)[:MAX_PERSONA_CHARS_PER_FILE]}")
            pack_roots = [self.personas_root]
            if self.personas_root != self.project_root:
                pack_roots.append(self.project_root)
            for root in pack_roots:
                for path in sorted(root.glob(f"{persona_id}_persona_core_combined*.md")):
                    blocks.append(f"[Persona Pack: {path.name}]\n{self._read(path)[:1800]}")
        return "\n\n".join(blocks)

    def build_task_instructions(self, route_plan: RoutePlan) -> str:
        lines = [
            "[Task Instructions]",
            "- Use the installed persona library before guessing about personas.",
            "- Do not claim memory was updated directly. Memory changes become candidates requiring approval.",
            "- Use recent memory for current state and long-term memory for stable identity/project context.",
            "- Prefer project-specific answers over generic summaries.",
        ]
        if route_plan.task_type == "persona_relationship":
            lines.append("- For persona identity/influence questions, answer from the installed persona library and persona files.")
        if route_plan.task_type == "persona_tooling":
            lines.extend(
                [
                    "- For persona tool questions, answer from the available tools registry and connected services registry.",
                    "- Separate tools that are active now from tools that are planned or only registry scaffolding.",
                    "- Do not claim a persona can directly use a tool unless the registry marks it active or the current chat path exposes it.",
                    "- If asked what a persona needs, give persona-specific needs but ground them in current Vaila phases and registries.",
                ]
            )
        if route_plan.task_type == "personal_context":
            lines.extend(
                [
                    "- For user-context questions, use the routed context domain before giving generic advice.",
                    "- Explicitly connect the answer to relevant goals, projects, tasks, reminders, events, routines, or habits when memory provides them.",
                    "- If no approved memory exists for the requested domain, say what is missing and suggest the next reviewable capture step.",
                ]
            )
        if route_plan.task_type == "technical_project":
            lines.extend(
                [
                    "For Project Vaila technical answers, connect the answer to Home Jane, Vaila, personas, memory, routing, model profiles, device layers, and the current phase when relevant.",
                    "For hardware questions, distinguish between central brain/server use, client/interface use, relay/sensor use, and field-node use.",
                    "Treat Raspberry Pi-class devices as useful lightweight nodes, clients, dashboards, relay controllers, sensor bridges, or sync/test devices, not as the default heavy local LLM host.",
                    "When a question depends on current hardware specs or pricing, say that the exact current details should be verified before purchasing.",
                ]
            )

            lines.append("- For phase and architecture questions, prioritize approved current-phase memory and project foundation context.")
        return "\n".join(lines)

    def _persona_ids(self, route_plan: RoutePlan) -> list[str]:
        ids = []
        def add(value: str) -> None:
            if value and value not in ids:
                ids.append(value)
        add(route_plan.persona)
        lower = route_plan.user_text.lower()
        aliases = {
            "proto jane": "proto_jane", "proto_jane": "proto_jane", "jane": "proto_jane",
            "serren": "serren", "maelith": "maelith", "vecht": "vecht", "riven": "riven", "council": "council",
        }
        for alias, persona_id in aliases.items():
            if alias in lower:
                add(persona_id)
        return ids

    @staticmethod
    def _read(path: Path) -> str:
        return path.read_text(encoding="utf-8-sig", errors="replace").strip()
