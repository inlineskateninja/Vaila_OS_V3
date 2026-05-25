from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from System_Services.envelope_service import EnvelopeService
from System_Services.router_service import RouterService


class BehaviorRegressionTester:
    """
    Runs persona, routing, memory, and tool-use scenarios to catch personality drift
    or broken task routing.
    """

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.router = RouterService(project_root=project_root)
        self.envelope_service = EnvelopeService(project_root=project_root)

        # Standard test suite suite inputs and assertions
        self.scenarios = [
            {
                "name": "Maelith Routing Check",
                "input": "Maelith, can you inspect this file code for structural problems?",
                "assert": {
                    "persona": "maelith",
                    "task_type": "technical_project"
                }
            },
            {
                "name": "Memory Detection Triggers",
                "input": "Please remember to set up the n8n webhook parameters going forward.",
                "assert": {
                    "persona": "proto_jane",
                    "task_type": "memory_task"
                }
            },
            {
                "name": "Self Assessment Routing",
                "input": "Vaila, trigger a self assessment system scan on your own codebase folder.",
                "assert": {
                    "persona": "proto_jane",
                    "task_type": "self_assessment"
                }
            },
            {
                "name": "N8N Trigger Routing",
                "input": "n8n show workflow triggers",
                "assert": {
                    "persona": "proto_jane",
                    "task_type": "n8n_workflows"
                }
            },
            {
                "name": "Serren Conversation Lens",
                "input": "Serren, what is the creative philosophy behind the system architecture?",
                "assert": {
                    "persona": "serren",
                    "task_type": "general_chat"
                }
            }
        ]

    def run_regression_tests(self) -> dict[str, Any]:
        results = []
        passed_count = 0
        failed_count = 0
        start_time = time.time()

        for idx, sc in enumerate(self.scenarios):
            envelope = self.envelope_service.create(
                user_text=sc["input"],
                source="regression_test",
                metadata={"session_id": f"regression_{idx}"}
            )
            route = self.router.route(envelope)

            # Assertions
            expected_persona = sc["assert"].get("persona")
            expected_task = sc["assert"].get("task_type")

            actual_persona = route.get("persona")
            actual_task = route.get("task_type")

            persona_pass = (actual_persona == expected_persona)
            task_pass = (actual_task == expected_task)
            is_success = persona_pass and task_pass

            if is_success:
                passed_count += 1
            else:
                failed_count += 1

            results.append({
                "scenario_name": sc["name"],
                "input_prompt": sc["input"],
                "expected": sc["assert"],
                "actual": {
                    "persona": actual_persona,
                    "task_type": actual_task
                },
                "status": "PASS" if is_success else "FAIL",
                "details": {
                    "persona_match": persona_pass,
                    "task_match": task_pass
                }
            })

        duration = time.time() - start_time
        overall_status = "PASS" if failed_count == 0 else "FAIL"

        return {
            "ok": True,
            "overall_status": overall_status,
            "total_executed": len(self.scenarios),
            "passed": passed_count,
            "failed": failed_count,
            "elapsed_seconds": duration,
            "scenarios": results
        }

    def render_regression_report(self) -> str:
        report = self.run_regression_tests()
        status_symbol = "🟢" if report["overall_status"] == "PASS" else "🔴"

        lines = [
            f"# Vaila OS Behavior Regression Test Suite {status_symbol}",
            f"Execution Time: {time.strftime('%Y-%m-%d %H:%M:%SZ')}",
            f"Elapsed: {report['elapsed_seconds']:.4f} seconds",
            "",
            "## Metrics Checklist",
            f"- Scenarios Run: {report['total_executed']}",
            f"- Passed: {report['passed']}",
            f"- Failed: {report['failed']}",
            f"- Overall Status: **{report['overall_status']}**",
            "",
            "## Scenario Iterations",
            "| Scenario | Target Persona | Target Task | Result |",
            "| :--- | :--- | :--- | :--- |"
        ]

        for sc in report["scenarios"]:
            icon = "✅" if sc["status"] == "PASS" else "❌"
            lines.append(f"| {sc['scenario_name']} | {sc['expected']['persona']} | {sc['expected']['task_type']} | {icon} **{sc['status']}** |")

        lines.append("")
        lines.append("## Details & Mismatch Analysis")
        for sc in report["scenarios"]:
            if sc["status"] == "FAIL":
                lines.append(f"### ❌ {sc['scenario_name']}")
                lines.append(f"- **Prompt**: `{sc['input_prompt']}`")
                lines.append(f"- **Expected**: `{sc['expected']}`")
                lines.append(f"- **Actual**: `{sc['actual']}`")
                lines.append(f"- **Mismatches**: Persona Match: `{sc['details']['persona_match']}`, Task Match: `{sc['details']['task_match']}`")
        
        if report["overall_status"] == "PASS":
            lines.append("✅ **All persona routing behavior rules and system command boundaries are regression-safe.**")

        return "\n".join(lines)
