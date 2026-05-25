from __future__ import annotations

import json
import sys
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
        perception_report = self._run_perception_scan()

        report = (
            "# Vaila OS V3 Self-Assessment Report\n\n"
            f"Generated UTC: {datetime.now(timezone.utc).isoformat()}\n\n"
            "## Missing Expected Top-Level Items\n\n"
            f"{missing if missing else 'None'}\n\n"
            "## System Perception Layer\n\n"
            f"{perception_report}\n\n"
            "## Directory Preview\n\n"
            f"{tree_preview}\n\n"
            "## Rule\n\n"
            "This report is observational only. Proposed patches must be exported to Sandbox/Proposed_Patches for approval.\n"
        )

        filename = datetime.now(timezone.utc).strftime("self_assessment_%Y%m%d_%H%M%S.md")
        output_path = self.export_dir / filename
        output_path.write_text(report, encoding="utf-8")

        return f"Self-assessment complete. Report exported to: {output_path}\n\n{report}"

    def _run_perception_scan(self) -> str:
        build_root = self.project_root / "Vaila_system_OS_Build"
        backend_path = build_root / "core_system_files" / "system_services" / "python_backend"
        if not backend_path.exists():
            return "Perception layer not found at Vaila_system_OS_Build/core_system_files/system_services/python_backend."

        backend_string = str(backend_path)
        if backend_string not in sys.path:
            sys.path.insert(0, backend_string)

        try:
            from app.services.system_health_service import SystemHealthService
        except Exception as exc:
            return f"Perception layer import failed: {exc}"

        try:
            health = SystemHealthService(project_root=build_root)
            config = health.introspection.default_config(max_file_size_bytes=256_000, max_scan_depth=8)
            config.llm_classification_max_files = 20
            summary = health.run_scan(config=config)
        except Exception as exc:
            return f"Perception scan failed: {exc}"

        categories = ", ".join(f"{key}: {value}" for key, value in sorted(summary.counts_by_category.items()))
        llm_status = self._latest_llm_classification_status(build_root)
        return (
            f"Perception scan complete. Files scanned: {summary.file_count}. "
            f"Issues detected: {len(summary.issues)}.\n\n"
            f"Categories: {categories or 'none'}.\n\n"
            f"LLM classification: {llm_status}"
        )

    def _latest_llm_classification_status(self, build_root: Path) -> str:
        inventory_path = build_root / "core_system_files" / "system_state" / "self_model" / "file_inventory.json"
        if not inventory_path.exists():
            return "no inventory file found after scan."

        try:
            payload = json.loads(inventory_path.read_text(encoding="utf-8"))
        except Exception as exc:
            return f"could not read inventory: {exc}"

        files = payload.get("files", [])
        llm_items = [item for item in files if item.get("metadata", {}).get("classification_source") == "llm"]
        if llm_items:
            model = llm_items[0].get("metadata", {}).get("llm_model", "unknown model")
            return f"{len(llm_items)} files classified by local LLM model {model}."

        first_error = next(
            (
                item.get("metadata", {}).get("llm_classification_error")
                for item in files
                if item.get("metadata", {}).get("llm_classification_error")
            ),
            "",
        )
        if first_error:
            return f"LLM classification was attempted but failed: {first_error}"
        return "LLM classification did not mark any files in the latest inventory."

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
            lines.append(f"{indent}- {marker} {relative.name}")
            count += 1

        return "\n".join(lines)
