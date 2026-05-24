from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


class SelfAssessmentTool:
    """
    Scans the project directory and exports a report to Sandbox.

    This tool does not modify core files.
    """

    EXPECTED_TOP_LEVEL = [
        "Core_System_Files",
        "System_Dogma",
        "System_Services",
        "System_Tools",
        "Connected_Services_Registry",
        "Tools_Registry",
        "Secrets",
        "Agent_Registry",
        "User",
        "Persona_Files",
        "Hardware_Profiles",
        "Device_Profiles",
        "LLM_Model_Profiles",
        "System_Wide_Memory",
        "System_Logging",
        "Sandbox",
        "tests",
        "config",
    ]

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.export_dir = project_root / "Sandbox" / "Self_Assessment_Exports"
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def run_self_assessment(self) -> str:
        missing = [
            name for name in self.EXPECTED_TOP_LEVEL
            if not (self.project_root / name).exists()
        ]

        tree_preview = self._tree_preview(max_items=300)

        report = (
            "# Vaila OS V3 Self-Assessment Report\n\n"
            f"Generated UTC: {datetime.now(timezone.utc).isoformat()}\n\n"
            "## Missing Expected Top-Level Items\n\n"
            f"{missing if missing else 'None'}\n\n"
            "## Directory Preview\n\n"
            "```text\n"
            f"{tree_preview}\n"
            "```\n\n"
            "## Rule\n\n"
            "This report is observational only. Proposed patches must be exported to Sandbox/Proposed_Patches for approval.\n"
        )

        filename = datetime.now(timezone.utc).strftime("self_assessment_%Y%m%d_%H%M%S.md")
        output_path = self.export_dir / filename
        output_path.write_text(report, encoding="utf-8")

        return f"Self-assessment complete. Report exported to: {output_path}\n\n{report}"

    def _tree_preview(self, max_items: int = 300) -> str:
        lines: list[str] = []
        count = 0

        for path in sorted(self.project_root.rglob("*")):
            if count >= max_items:
                lines.append("... preview truncated ...")
                break

            if any(part in {".git", ".venv", "__pycache__"} for part in path.parts):
                continue

            relative = path.relative_to(self.project_root)
            depth = len(relative.parts) - 1
            indent = "  " * depth
            marker = "[D]" if path.is_dir() else "[F]"
            lines.append(f"{indent}{marker} {relative.name}")
            count += 1

        return "\n".join(lines)
