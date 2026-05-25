import json
from pathlib import Path
from tempfile import TemporaryDirectory

from System_Tools.tool_registry_inspector import ToolRegistryInspector
from System_Tools.system_dependency_doctor import SystemDependencyDoctor
from System_Tools.memory_review_console import MemoryReviewConsole
from System_Tools.memory_backend_adapter import MemoryBackendAdapterFactory, JSONLAdapter
from System_Tools.self_model_diff_tool import SelfModelDiffTool
from System_Tools.capability_map_generator import CapabilityMapGenerator
from System_Tools.behavior_regression_tester import BehaviorRegressionTester
from System_Tools.patch_proposal_reviewer import PatchProposalReviewer
from System_Tools.goal_task_tracker import GoalTaskTracker
from System_Tools.n8n_workflow_librarian import N8NWorkflowLibrarian
from System_Tools.artifact_indexer import ArtifactIndexer
from System_Tools.safety_boundary_auditor import SafetyBoundaryAuditor
from System_Tools.persona_drift_monitor import PersonaDriftMonitor
from System_Tools.user_context_router import UserContextRouter
from System_Tools.self_evolution_planner import SelfEvolutionPlanner


def test_tool_registry_inspector():
    with TemporaryDirectory() as temp:
        root = Path(temp)
        
        # Seed registry folders
        reg_dir = root / "Tools_Registry"
        tools_dir = root / "System_Tools"
        reg_dir.mkdir()
        tools_dir.mkdir()

        # Seed configs
        (reg_dir / "available_tools.json").write_text(json.dumps({"tools": []}), encoding="utf-8")
        (reg_dir / "tool_permissions.json").write_text(json.dumps({"rules": []}), encoding="utf-8")
        (reg_dir / "tool_routes.json").write_text(json.dumps({"routes": {}}), encoding="utf-8")
        (tools_dir / "some_tool.py").write_text("class SomeTool:\n    pass\n", encoding="utf-8")

        inspector = ToolRegistryInspector(root)
        res = inspector.run_audit()
        assert res["ok"] is True
        assert len(res["issues"]) > 0  # Missing registration for some_tool.py
        
        report = inspector.render_report()
        assert "Audit Report" in report


def test_system_dependency_doctor():
    with TemporaryDirectory() as temp:
        root = Path(temp)
        
        (root / "requirements.txt").write_text("requests>=2.0.0\npython-dotenv>=1.0.0\n", encoding="utf-8")
        (root / ".env.example").write_text("LLM_BASE_URL=http://localhost:1234\n", encoding="utf-8")
        (root / ".env").write_text("LLM_BASE_URL=http://localhost:1234\n", encoding="utf-8")

        doctor = SystemDependencyDoctor(root)
        res = doctor.run_diagnostics()
        assert res["requirements_health"]["file_present"] is True
        assert "requests" in res["requirements_health"]["status"]

        report = doctor.render_report()
        assert "Dependency Doctor" in report


def test_memory_review_console_and_adapters():
    with TemporaryDirectory() as temp:
        root = Path(temp)
        (root / "data").mkdir()

        candidates_file = root / "data" / "openbrain_memory_candidates.jsonl"
        candidate_record = {
            "candidate_id": "ob_test_123",
            "status": "needs_user_review",
            "payload": {
                "text": "Remember to use virtual environment inside the workspace.",
                "source": "unittest"
            }
        }
        candidates_file.write_text(json.dumps(candidate_record) + "\n", encoding="utf-8")

        console = MemoryReviewConsole(root)
        candidates = console.list_reviewable_candidates()
        assert len(candidates) == 1
        assert candidates[0]["candidate_id"] == "ob_test_123"

        # Edit candidate text
        ok = console.edit_candidate_payload("ob_test_123", "New text preference.")
        assert ok is True

        # Promote candidate to durable memory
        res = console.promote_candidate("ob_test_123", category="coding", project_only=True)
        assert res["ok"] is True
        assert res["memory"]["category"] == "coding"
        assert res["memory"]["project_only"] is True

        # Search memories using JSONL adapter
        adapter = JSONLAdapter(root)
        search_res = adapter.search_memories(query="preference")
        assert len(search_res) == 1
        assert "New text preference" in search_res[0]["text"]


def test_self_model_diff_tool():
    with TemporaryDirectory() as temp:
        root = Path(temp)
        exp_dir = root / "Sandbox" / "Self_Assessment_Exports"
        exp_dir.mkdir(parents=True)

        report1 = (
            "# Vaila OS V3 Self-Assessment Report\n\n"
            "Generated UTC: 2026-05-24T03:00:00Z\n\n"
            "## Missing Expected Top-Level Items\n\n"
            "['Connected_Services_Registry']\n\n"
            "Perception scan complete. Files scanned: 100. Issues detected: 5.\n\n"
            "Categories: env: 2, imports: 3.\n"
        )
        report2 = (
            "# Vaila OS V3 Self-Assessment Report\n\n"
            "Generated UTC: 2026-05-25T03:00:00Z\n\n"
            "## Missing Expected Top-Level Items\n\n"
            "None\n\n"
            "Perception scan complete. Files scanned: 110. Issues detected: 2.\n\n"
            "Categories: env: 1, imports: 1.\n"
        )

        (exp_dir / "self_assessment_20260524_030000.md").write_text(report1, encoding="utf-8")
        (exp_dir / "self_assessment_20260525_030000.md").write_text(report2, encoding="utf-8")

        diff_tool = SelfModelDiffTool(root)
        res = diff_tool.calculate_diffs()
        assert res["ok"] is True
        assert res["comparison"]["trend"] == "improving"
        assert "Connected_Services_Registry" in res["comparison"]["recovered_items"]

        report = diff_tool.render_diff_report()
        assert "Self-Model Diff & Drift Report" in report


def test_capability_map_generator():
    with TemporaryDirectory() as temp:
        root = Path(temp)
        (root / "System_Tools").mkdir()
        (root / "System_Services").mkdir()
        (root / "Core_System_Files").mkdir()
        (root / "tests").mkdir()
        (root / "Persona_Files" / "Proto_Jane").mkdir(parents=True)

        (root / "System_Tools" / "test_tool.py").write_text("class TestTool:\n    pass\n", encoding="utf-8")
        (root / "System_Services" / "test_service.py").write_text("class TestService:\n    pass\n", encoding="utf-8")
        (root / "Core_System_Files" / "local_api.py").write_text('@app.get("/api/test")\ndef test_route():\n    pass\n', encoding="utf-8")
        (root / "tests" / "test_dummy.py").write_text("def test_dummy_run():\n    assert True\n", encoding="utf-8")

        generator = CapabilityMapGenerator(root)
        res = generator.generate_map()
        assert res["tools_count"] == 1
        assert res["services_count"] == 1
        assert res["endpoints_count"] == 1
        assert res["tests_count"] == 1

        chart = generator.render_mermaid_flowchart()
        assert "mermaid" in chart


def test_goal_task_tracker():
    with TemporaryDirectory() as temp:
        root = Path(temp)
        tracker = GoalTaskTracker(root)
        
        goal = tracker.add_goal("Write Advanced Tools", description="Core system installation task", priority="high")
        assert goal["title"] == "Write Advanced Tools"
        assert goal["priority"] == "high"

        # Add subtask
        ok = tracker.add_subtask(goal["id"], "Write GoalTaskTracker")
        assert ok is True

        # Add blocker
        ok = tracker.add_blocker(goal["id"], "Need user approval on plan")
        assert ok is True

        state = tracker.load_state()
        assert state["goals"][0]["status"] == "blocked"

        board = tracker.render_kanban_board()
        assert "Kanban Task Board" in board


def test_n8n_workflow_librarian():
    with TemporaryDirectory() as temp:
        root = Path(temp)
        lib = N8NWorkflowLibrarian(root)

        workflow_data = {
            "name": "Consensus Backups Trigger",
            "nodes": [
                {"type": "n8n-nodes-base.webhook", "name": "Webhook Trigger"},
                {"type": "n8n-nodes-base.if", "name": "Security Check", "parameters": {"conditions": {"string": [{"value1": "={{ $headers[\"x-vaila-webhook-secret\"] }}", "value2": "secret"}]}}}
            ]
        }
        (root / "Sandbox" / "n8n_Workflow_Library" / "consensus_backup.json").write_text(json.dumps(workflow_data), encoding="utf-8")

        w_list = lib.list_library_workflows()
        assert len(w_list) == 1
        assert w_list[0]["valid"] is True

        doc = lib.document_workflow("consensus_backup.json")
        assert "n8n Workflow Library Documentation" in doc


def test_artifact_indexer():
    with TemporaryDirectory() as temp:
        root = Path(temp)
        indexer = ArtifactIndexer(root)

        (root / "data" / "artifacts" / "council_synthesis_20260525.md").write_text("# Consensus Report\nThis is a synthesized consensus report of the council.", encoding="utf-8")
        
        res = indexer.build_index()
        assert res["total_indexed"] == 1

        search_res = indexer.search_index("synthesis")
        assert len(search_res) == 1
        assert search_res[0]["filename"] == "council_synthesis_20260525.md"


def test_safety_boundary_auditor():
    with TemporaryDirectory() as temp:
        root = Path(temp)
        (root / "System_Tools").mkdir()
        (root / "System_Dogma").mkdir()
        (root / "Tools_Registry").mkdir()

        (root / "System_Dogma" / "safety_boundaries.md").write_text("- Do not delete core system files.\n", encoding="utf-8")
        (root / "Tools_Registry" / "tool_permissions.json").write_text(json.dumps({
            "rules": [
                {"tool_id": "unsafe_tool", "can_write_core_files": True}
            ]
        }), encoding="utf-8")
        (root / "System_Tools" / "unsafe_tool.py").write_text("import subprocess\nclass UnsafeTool:\n    def delete(self):\n        os.remove('core_file.py')\n", encoding="utf-8")

        auditor = SafetyBoundaryAuditor(root)
        res = auditor.audit_boundaries()
        assert res["is_secure"] is False
        assert len(res["violations"]) > 0

        report = auditor.render_safety_report()
        assert "Dogma Audit Report" in report


def test_persona_drift_monitor():
    with TemporaryDirectory() as temp:
        root = Path(temp)
        (root / "Persona_Files" / "Proto_Jane").mkdir(parents=True)
        (root / "Persona_Files" / "Proto_Jane" / "behavior_rules.md").write_text("- Be direct and operating-system like.\n", encoding="utf-8")

        monitor = PersonaDriftMonitor(root)
        res = monitor.audit_persona("proto_jane", "Vaila OS system direct check operation stable.")
        assert res["ok"] is True
        assert res["status"] == "STABLE"


def test_user_context_router():
    with TemporaryDirectory() as temp:
        root = Path(temp)
        router = UserContextRouter(root)
        
        ok = router.log_routing_event(
            prompt="Hello Vaila, run a python script.",
            loaded_modules=["coding_preferences"],
            matched_keywords={"coding_preferences": ["python"]},
            context_size_chars=400
        )
        assert ok is True

        analysis = router.run_route_analysis()
        assert analysis["total_routing_events"] == 1
        assert "coding_preferences" in analysis["most_active_modules"]


def test_self_evolution_planner():
    with TemporaryDirectory() as temp:
        root = Path(temp)
        (root / "System_Tools").mkdir()
        (root / "System_Dogma").mkdir()
        (root / "Tools_Registry").mkdir()
        (root / "data" / "artifacts").mkdir(parents=True)
        (root / "Sandbox" / "Self_Assessment_Exports").mkdir(parents=True)

        (root / "requirements.txt").write_text("requests>=2.0.0\n", encoding="utf-8")
        (root / "System_Dogma" / "safety_boundaries.md").write_text("- Do not delete core system files.\n", encoding="utf-8")
        (root / "Tools_Registry" / "available_tools.json").write_text(json.dumps({"tools": []}), encoding="utf-8")
        (root / "Tools_Registry" / "tool_permissions.json").write_text(json.dumps({"rules": []}), encoding="utf-8")
        (root / "Tools_Registry" / "tool_routes.json").write_text(json.dumps({"routes": {}}), encoding="utf-8")

        planner = SelfEvolutionPlanner(root)
        res = planner.formulate_plan()
        assert res["ok"] is True
        assert res["proposals_count"] > 0

        plan_desc = planner.render_evolution_report()
        assert "Self-Evolution & Ranked Roadmaps" in plan_desc
