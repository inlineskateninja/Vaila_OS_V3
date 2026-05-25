from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.models.system_perception_models import SystemRepairPacket, SystemRepairPacketBatch, utc_timestamp


GENERAL_ALLOWED_ACTIONS = [
    "Inspect relevant source files.",
    "Make minimal code changes.",
    "Add or update tests.",
    "Update documentation if directly relevant.",
    "Preserve existing behavior unless the recommendation requires a targeted change.",
]

GENERAL_FORBIDDEN_ACTIONS = [
    "Do not delete files unless explicitly approved by Malik.",
    "Do not scan the whole computer.",
    "Do not read secrets.",
    "Do not modify .env files.",
    "Do not change persona identity files unless the recommendation specifically targets persona infrastructure and Malik approves.",
    "Do not alter memory policy without explicit approval.",
    "Do not add autonomous self-repair.",
    "Do not claim consciousness or subjective awareness.",
    "Do not invent capabilities.",
]


class SystemRepairPacketService:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).resolve()
        self.self_model_dir = self.project_root / "core_system_files" / "system_state" / "self_model"
        self.packet_dir = self.project_root / "core_system_files" / "system_state" / "repair_packets"
        self.index_path = self.self_model_dir / "repair_packet_index.json"

    def load_latest_recommendation_plan(self) -> dict[str, Any] | None:
        path = self.self_model_dir / "recommendation_plan.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def load_repair_packet_index(self) -> dict[str, Any]:
        if not self.index_path.exists():
            return {"packets": []}
        return json.loads(self.index_path.read_text(encoding="utf-8"))

    def load_latest_packet(self) -> dict[str, Any] | None:
        index = self.load_repair_packet_index()
        packets = index.get("packets", [])
        if not packets:
            return None
        latest = packets[-1]
        json_path = Path(latest.get("json_path", ""))
        markdown_path = Path(latest.get("markdown_path", ""))
        if not json_path.exists():
            return latest
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        payload["markdown"] = markdown_path.read_text(encoding="utf-8") if markdown_path.exists() else ""
        payload["metadata"] = latest
        return payload

    def select_recommendations(self, plan: dict[str, Any], mode: str = "top", limit: int = 1) -> list[dict[str, Any]]:
        recommendations = list(plan.get("recommendations", []))
        if not recommendations:
            top = plan.get("top_recommendation") or {}
            recommendations = [top] if top else []

        if mode == "top":
            selected = recommendations[:1]
        elif mode in {"critical", "high"}:
            selected = [item for item in recommendations if item.get("priority") == mode]
        elif mode == "safe":
            selected = [item for item in recommendations if item.get("safe_to_delegate_to_codex") is True]
        elif mode == "all":
            selected = recommendations
        else:
            selected = recommendations[:1]

        if limit <= 0:
            limit = 1
        if mode == "all" and limit > 10:
            limit = 10
        return selected[:limit]

    def create_repair_packet(self, recommendation: dict[str, Any]) -> SystemRepairPacket:
        title = recommendation.get("title", "Untitled repair recommendation")
        packet_id = self._packet_id(recommendation)
        allowed_actions = self._allowed_actions(recommendation)
        forbidden_actions = self._forbidden_actions(recommendation)
        implementation_steps = self._implementation_steps(recommendation)
        tests_to_run = self._tests_to_run(recommendation)
        acceptance_criteria = self._acceptance_criteria(recommendation)
        context = (
            "This packet is a proposed task generated from the latest Vaila recommendation plan. "
            "User approval is required before implementation. The packet does not apply changes by itself."
        )
        goal = recommendation.get("suggested_action") or f"Address recommendation: {title}"
        packet_data = {
            "packet_id": packet_id,
            "created_at": utc_timestamp(),
            "source_recommendation_id": recommendation.get("id", ""),
            "title": title,
            "priority": recommendation.get("priority", "medium"),
            "severity": recommendation.get("severity", "inconvenient"),
            "category": recommendation.get("category", "unknown"),
            "status": "drafted",
            "requires_user_approval": True,
            "safe_to_delegate_to_codex": bool(recommendation.get("safe_to_delegate_to_codex", False)),
            "goal": goal,
            "context": context,
            "evidence": recommendation.get("evidence", []),
            "affected_files": recommendation.get("affected_files", []),
            "allowed_actions": allowed_actions,
            "forbidden_actions": forbidden_actions,
            "implementation_steps": implementation_steps,
            "tests_to_run": tests_to_run,
            "acceptance_criteria": acceptance_criteria,
            "rollback_notes": [
                "Do not apply this packet automatically.",
                "If implementation causes test failures, revert only the targeted changes after user approval.",
            ],
            "codex_prompt": "",
        }
        packet_data["codex_prompt"] = self._codex_prompt(packet_data)
        return SystemRepairPacket(**packet_data)

    def create_repair_packets(self, mode: str = "top", limit: int = 1) -> SystemRepairPacketBatch:
        plan = self.load_latest_recommendation_plan()
        if plan is None:
            return SystemRepairPacketBatch(
                status="no_data",
                created_at=utc_timestamp(),
                mode=mode,
                limit=limit,
                notes=["No recommendation plan exists yet. Generate recommendations first, then create repair packets."],
            )

        selected = self.select_recommendations(plan, mode=mode, limit=limit)
        packets = [self.create_repair_packet(recommendation) for recommendation in selected]
        metadata = [self.save_repair_packet(packet.model_dump()) for packet in packets]
        return SystemRepairPacketBatch(
            status="created" if packets else "no_data",
            created_at=utc_timestamp(),
            mode=mode,
            limit=limit,
            packets=packets,
            packet_metadata=metadata,
            notes=[] if packets else ["The recommendation plan contained no matching recommendations for the selected mode."],
        )

    def save_repair_packet(self, packet: dict[str, Any]) -> dict[str, Any]:
        self.packet_dir.mkdir(parents=True, exist_ok=True)
        slug = self._slug(packet.get("title", "repair_packet"))
        from datetime import UTC, datetime

        stamp = datetime.now(UTC).strftime("%Y_%m_%d_%H%M%S_%f")
        base = f"repair_packet_{stamp}_{slug}"
        json_path = self.packet_dir / f"{base}.json"
        markdown_path = self.packet_dir / f"{base}.md"
        json_path.write_text(json.dumps(packet, indent=2), encoding="utf-8")
        markdown_path.write_text(self.save_repair_packet_markdown(packet), encoding="utf-8")

        metadata = {
            "packet_id": packet.get("packet_id", ""),
            "title": packet.get("title", ""),
            "priority": packet.get("priority", ""),
            "severity": packet.get("severity", ""),
            "category": packet.get("category", ""),
            "requires_user_approval": True,
            "safe_to_delegate_to_codex": bool(packet.get("safe_to_delegate_to_codex", False)),
            "json_path": str(json_path),
            "markdown_path": str(markdown_path),
            "created_at": packet.get("created_at", ""),
        }
        self.update_repair_packet_index(metadata)
        return metadata

    def save_repair_packet_markdown(self, packet: dict[str, Any]) -> str:
        return "\n".join(
            [
                f"# {packet.get('title', 'Repair Packet')}",
                "",
                f"- Packet ID: {packet.get('packet_id', '')}",
                f"- Priority: {packet.get('priority', '')}",
                f"- Severity: {packet.get('severity', '')}",
                f"- Requires user approval: {packet.get('requires_user_approval', True)}",
                f"- Safe to delegate to Codex: {packet.get('safe_to_delegate_to_codex', False)}",
                "",
                "## Context",
                packet.get("context", ""),
                "",
                "## Goal",
                packet.get("goal", ""),
                "",
                "## Codex Prompt",
                "```text",
                packet.get("codex_prompt", ""),
                "```",
                "",
            ]
        )

    def update_repair_packet_index(self, packet_metadata: dict[str, Any]) -> None:
        self.self_model_dir.mkdir(parents=True, exist_ok=True)
        index = self.load_repair_packet_index()
        packets = index.setdefault("packets", [])
        packets.append(packet_metadata)
        index["updated_at"] = utc_timestamp()
        self.index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")

    def format_repair_packet_summary(self, packet: dict[str, Any]) -> str:
        return (
            f"Created repair packet: {packet.get('title')}. "
            f"Priority: {packet.get('priority')}. "
            f"Requires user approval: {packet.get('requires_user_approval', True)}. "
            f"Safe to delegate to Codex: {packet.get('safe_to_delegate_to_codex', False)}."
        )

    def format_batch_summary(self, batch: dict[str, Any] | SystemRepairPacketBatch) -> str:
        if isinstance(batch, SystemRepairPacketBatch):
            batch = batch.model_dump()
        if batch.get("status") == "no_data":
            notes = batch.get("notes") or []
            return notes[0] if notes else "No recommendation plan exists yet. Generate recommendations first, then create repair packets."
        count = len(batch.get("packets", []))
        if count == 0:
            return "No repair packets were created for the selected mode."
        first = batch["packets"][0]
        safe = first.get("safe_to_delegate_to_codex", False)
        return (
            f"Created {count} repair packet{'s' if count != 1 else ''} from the selected recommendations. "
            f"The packet requires user approval and is marked {'safe' if safe else 'not safe'} to delegate to Codex."
        )

    def _allowed_actions(self, recommendation: dict[str, Any]) -> list[str]:
        actions = list(GENERAL_ALLOWED_ACTIONS)
        category = recommendation.get("category", "")
        if category in {"missing_router", "missing_service", "missing_model_schema", "missing_expected_file"}:
            actions.append("Add deterministic wiring or bridge files directly related to the recommendation.")
        if category in {"broken_import", "stale_bridge_path"}:
            actions.append("Clean up targeted import paths.")
        if category in {"documentation"}:
            actions.append("Update directly relevant documentation.")
        return actions

    def _forbidden_actions(self, recommendation: dict[str, Any]) -> list[str]:
        actions = list(GENERAL_FORBIDDEN_ACTIONS)
        if recommendation.get("safe_to_delegate_to_codex") is False:
            actions.append("Do not implement this recommendation until Malik explicitly approves the specific change plan.")
        return actions

    def _implementation_steps(self, recommendation: dict[str, Any]) -> list[str]:
        affected = recommendation.get("affected_files", [])
        steps = [
            "Review the source recommendation and evidence.",
            "Inspect only the relevant project files.",
            "Make the smallest targeted change that satisfies the recommendation.",
            "Add or update focused regression tests.",
            "Run the relevant tests and report results.",
        ]
        if affected:
            steps.insert(1, "Inspect affected files: " + ", ".join(affected))
        return steps

    def _tests_to_run(self, recommendation: dict[str, Any]) -> list[str]:
        tests = ["python -m pytest"]
        category = recommendation.get("category", "")
        if category in {"missing_router", "missing_service", "missing_model_schema", "missing_expected_file"}:
            tests.insert(0, "python -m pytest Vaila_system_OS_Build\\core_system_files\\system_services\\python_backend\\tests")
        return tests

    def _acceptance_criteria(self, recommendation: dict[str, Any]) -> list[str]:
        return [
            "The targeted recommendation is addressed or clearly reported as blocked.",
            "Existing perception routes still respond successfully.",
            "Existing tests pass.",
            "No persona identity files are modified unless explicitly approved.",
            "No autonomous repair behavior is added.",
        ]

    def _codex_prompt(self, packet: dict[str, Any]) -> str:
        return "\n".join(
            [
                f"Task: {packet['title']}",
                "",
                "Context:",
                packet["context"],
                "",
                "Goal:",
                packet["goal"],
                "",
                "Files likely involved:",
                self._bullet_list(packet["affected_files"]),
                "",
                "Allowed actions:",
                self._bullet_list(packet["allowed_actions"]),
                "",
                "Forbidden actions:",
                self._bullet_list(packet["forbidden_actions"]),
                "",
                "Implementation steps:",
                self._numbered_list(packet["implementation_steps"]),
                "",
                "Tests to add or update:",
                self._bullet_list(packet["tests_to_run"]),
                "",
                "Acceptance criteria:",
                self._bullet_list(packet["acceptance_criteria"]),
                "",
                "Required final report:",
                "- Files changed",
                "- Tests run",
                "- Outcome",
                "- Any blockers or assumptions",
            ]
        )

    @staticmethod
    def _bullet_list(items: list[str]) -> str:
        return "\n".join(f"- {item}" for item in items) if items else "- None listed"

    @staticmethod
    def _numbered_list(items: list[str]) -> str:
        return "\n".join(f"{index}. {item}" for index, item in enumerate(items, start=1))

    def _packet_id(self, recommendation: dict[str, Any]) -> str:
        import hashlib

        raw = "|".join([recommendation.get("id", ""), recommendation.get("title", ""), recommendation.get("category", "")])
        return "repair_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]

    @staticmethod
    def _slug(value: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.lower()).strip("_")
        return slug[:60] or "repair_packet"
