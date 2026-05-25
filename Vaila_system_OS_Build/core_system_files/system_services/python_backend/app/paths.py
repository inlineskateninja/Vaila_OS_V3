from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VailaPaths:
    project_root: Path
    system_os_root: Path
    memory_root: Path
    candidate_root: Path
    model_profiles_path: Path
    activity_log_path: Path
    model_eval_path: Path
    tool_result_path: Path
    import_report_path: Path
    persona_root: Path
    foundation_root: Path
    memory_recall_log_path: Path
    sqlite_db_path: Path


def find_project_root(start: str | Path | None = None) -> Path:
    current = Path(start or __file__).resolve()
    if current.is_file():
        current = current.parent
    for candidate in [current, *current.parents]:
        if (candidate / "vaila_system_os" / "system_manifest.json").exists():
            return candidate
    return Path.cwd()


def get_vaila_paths(project_root: str | Path) -> VailaPaths:
    root = Path(project_root)
    system_root = root / "vaila_system_os"
    use_system_layout = system_root.exists()

    if not use_system_layout:
        data_root = root / "data"
        return VailaPaths(
            project_root=root,
            system_os_root=system_root,
            memory_root=data_root / "memory",
            candidate_root=data_root / "memory_candidates",
            model_profiles_path=data_root / "model_profiles.json",
            activity_log_path=data_root / "logs" / "activity.jsonl",
            model_eval_path=data_root / "logs" / "model_evaluation.jsonl",
            tool_result_path=data_root / "tool_results" / "recent.jsonl",
            import_report_path=data_root / "imports" / "reports" / "import_reports.jsonl",
            persona_root=root / "personas",
            foundation_root=root,
            memory_recall_log_path=data_root / "logs" / "memory_recall.jsonl",
            sqlite_db_path=data_root / "vaila_memory.sqlite3",
        )

    return VailaPaths(
        project_root=root,
        system_os_root=system_root,
        memory_root=system_root / "system_wide_memory" / "user_saved_memories",
        candidate_root=system_root / "sandbox" / "memory_candidates",
        model_profiles_path=system_root / "core_system_files" / "system_services" / "runtime_services" / "model_profiles.json",
        activity_log_path=system_root / "system_logging" / "session_logs" / "activity.jsonl",
        model_eval_path=system_root / "system_logging" / "failure_logs" / "model_evaluation.jsonl",
        tool_result_path=system_root / "system_logging" / "router_logs" / "tool_results_recent.jsonl",
        import_report_path=system_root / "system_logging" / "session_logs" / "import_reports.jsonl",
        persona_root=system_root / "persona_files",
        foundation_root=system_root / "core_system_files" / "system_dogma",
        memory_recall_log_path=system_root / "system_logging" / "session_logs" / "memory_recall.jsonl",
        sqlite_db_path=system_root / "device_storage" / "vaila_memory.sqlite3",
    )
