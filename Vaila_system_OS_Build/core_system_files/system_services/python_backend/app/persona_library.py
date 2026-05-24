from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class PersonaInfo:
    persona_id: str
    display_name: str
    role: str = ""
    pronouns: str = ""
    source_path: str = ""
    files: list[str] = field(default_factory=list)
    influences: list[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PersonaLibrary:
    def __init__(self, project_root: str | Path, personas_root: str | Path | None = None):
        self.project_root = Path(project_root)
        self.personas_root = Path(personas_root) if personas_root else self.project_root / "personas"
        self.personas: dict[str, PersonaInfo] = {}

    def load(self) -> None:
        self.personas.clear()
        if self.personas_root.exists():
            for persona_dir in sorted(path for path in self.personas_root.iterdir() if path.is_dir()):
                info = self._load_persona_dir(persona_dir)
                self.personas[info.persona_id] = info

        # Built-ins that may not have folders yet.
        self._ensure_builtin("proto_jane", "Proto Jane", "system-level coordinator", "she/her")
        self._ensure_builtin("vecht", "Vecht", "strategic protector and asset guardian", "he/him")
        self._ensure_builtin("riven", "Riven", "critique and analysis lens", "he/him")
        self._ensure_builtin("council", "Council", "structured multi-perspective review mode", "they/them")

        self._load_combined_persona_packs()

    def list_personas(self) -> list[PersonaInfo]:
        if not self.personas:
            self.load()
        return [self.personas[key] for key in sorted(self.personas)]

    def get(self, persona_id: str) -> PersonaInfo | None:
        if not self.personas:
            self.load()
        return self.personas.get(persona_id)

    def find_by_influence(self, influence: str) -> list[PersonaInfo]:
        if not self.personas:
            self.load()
        needle = influence.lower()
        matches = []
        for info in self.personas.values():
            if any(needle in item.lower() for item in info.influences):
                matches.append(info)
        return matches

    def to_context_block(self) -> str:
        infos = self.list_personas()
        lines = ["[Installed Personas Library]"]
        for info in infos:
            influence_text = "; ".join(info.influences[:3]) if info.influences else "none documented"
            lines.append(f"- {info.display_name} ({info.persona_id}): {info.role}. Influences: {influence_text}.")
        return "\n".join(lines)

    def _load_persona_dir(self, persona_dir: Path) -> PersonaInfo:
        persona_id = persona_dir.name
        manifest = persona_dir / "manifest.yaml"
        data = manifest.read_text(encoding="utf-8", errors="replace") if manifest.exists() else ""
        display_name = self._field(data, "display_name") or persona_id.replace("_", " ").title()
        role = self._field(data, "role")
        pronouns = self._field(data, "pronouns")
        files = [str(path.relative_to(self.project_root)) for path in sorted(persona_dir.iterdir()) if path.is_file()]
        all_text = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in sorted(persona_dir.iterdir()) if path.is_file())
        influences = self._extract_influences(all_text)
        return PersonaInfo(
            persona_id=persona_id,
            display_name=display_name,
            role=role,
            pronouns=pronouns,
            source_path=str(persona_dir.relative_to(self.project_root)),
            files=files,
            influences=influences,
            summary=self._first_sentence(all_text),
        )

    def _ensure_builtin(self, persona_id: str, display_name: str, role: str, pronouns: str) -> None:
        if persona_id not in self.personas:
            self.personas[persona_id] = PersonaInfo(
                persona_id=persona_id,
                display_name=display_name,
                role=role,
                pronouns=pronouns,
                source_path="built-in",
            )

    def _load_combined_persona_packs(self) -> None:
        pack_roots = [self.personas_root]
        if self.personas_root != self.project_root:
            pack_roots.append(self.project_root)
        seen: set[Path] = set()
        for root in pack_roots:
            for path in sorted(root.glob("*_persona_core_combined*.md")):
                if path in seen:
                    continue
                seen.add(path)
                text = path.read_text(encoding="utf-8", errors="replace")
                persona_id = path.name.split("_persona_core_combined", 1)[0]
                info = self.personas.get(persona_id)
                if info is None:
                    info = PersonaInfo(
                        persona_id=persona_id,
                        display_name=persona_id.replace("_", " ").title(),
                        source_path=str(path.relative_to(self.project_root)),
                    )
                    self.personas[persona_id] = info
                found = self._extract_influences(text)
                for item in found:
                    if item not in info.influences:
                        info.influences.append(item)
                if not info.summary:
                    info.summary = self._first_sentence(text)

    @staticmethod
    def _field(text: str, key: str) -> str:
        match = re.search(rf"^\s*{re.escape(key)}\s*:\s*(.+?)\s*$", text, flags=re.MULTILINE)
        return match.group(1).strip().strip('"') if match else ""

    @staticmethod
    def _extract_influences(text: str) -> list[str]:
        influences: list[str] = []
        lines = text.splitlines()
        capture = False
        for line in lines:
            lower = line.lower().strip()
            if any(term in lower for term in ["influence", "inspirations", "inspired by"]):
                capture = True
                continue
            if capture:
                if lower.startswith("#") and influences:
                    break
                if line.strip().startswith("-"):
                    item = line.strip().lstrip("-").strip()
                    if item and item not in influences:
                        influences.append(item)
                elif not line.strip() and influences:
                    break
        # Fallback direct character detection.
        for name in ["Naota", "Kaworu", "Renton"]:
            if name.lower() in text.lower() and not any(name.lower() in item.lower() for item in influences):
                influences.append(name)
        return influences[:12]

    @staticmethod
    def _first_sentence(text: str) -> str:
        clean = re.sub(r"\s+", " ", text).strip()
        if not clean:
            return ""
        return clean[:260]
