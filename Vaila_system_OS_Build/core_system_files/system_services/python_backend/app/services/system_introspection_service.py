from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from app.models.system_perception_models import (
    DirectoryScanConfig,
    DirectoryScanResult,
    FileInventoryItem,
    as_posix_relative,
    utc_timestamp,
)


DEFAULT_ALLOWED_ROOTS = [
    "vaila_system_os",
    "personas",
    "memory",
    "config",
    "tests",
    "core_system_files",
    "persona_files",
    "system_wide_memory",
]

DEFAULT_IGNORED_FOLDERS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "models",
    "model_files",
    "audio_cache",
    "tts_cache",
    "temp",
    "old",
}

DEFAULT_IGNORED_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".wav",
    ".mp3",
    ".onnx",
    ".gguf",
    ".bin",
    ".pt",
    ".safetensors",
    ".zip",
}

SECRET_NAMES = {".env", ".env.example", "secrets", "secret", "credentials", "token"}
DEPRECATED_IMPORT_MARKERS = [
    ".".join(["vaila_system_os", "core_system_files", "system_services", "python_backend", "app"]),
    "from " + "core_system_files.",
    "import " + "core_system_files.",
]


class SystemIntrospectionService:
    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = Path(project_root).resolve() if project_root else self.default_project_root()
        self.state_root = self.project_root / "core_system_files" / "system_state"
        self.self_model_dir = self.state_root / "self_model"
        self.scan_reports_dir = self.state_root / "scan_reports"

    @staticmethod
    def default_project_root() -> Path:
        return Path(__file__).resolve().parents[5]

    def default_config(
        self,
        max_file_size_bytes: int = 512_000,
        max_scan_depth: int = 8,
    ) -> DirectoryScanConfig:
        return DirectoryScanConfig(
            project_root=str(self.project_root),
            allowed_roots=DEFAULT_ALLOWED_ROOTS,
            ignored_folders=sorted(DEFAULT_IGNORED_FOLDERS),
            ignored_extensions=sorted(DEFAULT_IGNORED_EXTENSIONS),
            max_file_size_bytes=max_file_size_bytes,
            max_scan_depth=max_scan_depth,
            read_small_python_files=True,
        )

    def scan(
        self,
        config: DirectoryScanConfig | None = None,
        save_report: bool = True,
    ) -> DirectoryScanResult:
        config = config or self.default_config()
        allowed_roots = self._existing_allowed_roots(config.allowed_roots)
        files: list[FileInventoryItem] = []
        skipped: list[dict[str, Any]] = []

        for root in allowed_roots:
            for path in root.rglob("*"):
                if path.is_dir():
                    continue

                relative = as_posix_relative(path, self.project_root)
                if self._should_skip_path(path, config, skipped):
                    continue

                depth = len(Path(relative).parts)
                if depth > config.max_scan_depth:
                    skipped.append({"path": relative, "reason": "max_scan_depth"})
                    continue

                try:
                    stat = path.stat()
                except OSError as exc:
                    skipped.append({"path": relative, "reason": f"stat_failed: {exc}"})
                    continue

                if stat.st_size > config.max_file_size_bytes:
                    skipped.append({"path": relative, "reason": "max_file_size_bytes"})
                    continue

                category = self.classify_file(path)
                metadata = self._metadata_for(path, category, config)
                files.append(
                    FileInventoryItem(
                        path=relative,
                        name=path.name,
                        extension=path.suffix.lower(),
                        size_bytes=stat.st_size,
                        modified_time=self._mtime_iso(stat.st_mtime),
                        category=category,
                        metadata=metadata,
                    )
                )

        counts = dict(Counter(item.category for item in files))
        result = DirectoryScanResult(
            ok=True,
            scanned_at=utc_timestamp(),
            project_root=str(self.project_root),
            config=config,
            files=sorted(files, key=lambda item: item.path),
            skipped=skipped,
            counts_by_category=counts,
        )

        if save_report:
            result.report_path = str(self.save_scan_report(result))

        return result

    def save_scan_report(self, result: DirectoryScanResult) -> Path:
        self.scan_reports_dir.mkdir(parents=True, exist_ok=True)
        from datetime import UTC, datetime

        stamp = datetime.now(UTC).strftime("%Y_%m_%d_%H%M%S_%f")
        path = self.scan_reports_dir / f"scan_{stamp}.json"
        path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        return path

    def classify_file(self, path: Path) -> str:
        relative = as_posix_relative(path, self.project_root).lower()
        name = path.name.lower()
        suffix = path.suffix.lower()
        parts = set(Path(relative).parts)

        if name in {"app.py", "main.py", "service.py", "run_service.py"} and "core_system_files" in parts:
            return "core_entrypoint"
        if name in {"router.py"} or "/routers/" in f"/{relative}/" or name.endswith("_router.py"):
            return "router"
        if "/services/" in f"/{relative}/" or name.endswith("_service.py") or name in {"core.py", "llm_client.py"}:
            return "service"
        if "/models/" in f"/{relative}/" or name in {"schemas.py"} or name.endswith("_models.py"):
            return "model_schema"
        if name == "manifest.json" and ("personas" in parts or "persona_files" in parts):
            return "persona_manifest"
        if ("personas" in parts or "persona_files" in parts) and suffix in {".md", ".json"}:
            return "persona_policy"
        if "memory" in parts or "system_wide_memory" in parts or "memory" in relative:
            return "memory_file"
        if "config" in parts or name.endswith("_config.json") or suffix in {".toml", ".yaml", ".yml"}:
            return "config_file"
        if "tests" in parts or name.startswith("test_"):
            return "test_file"
        if suffix in {".md", ".txt", ".rst"}:
            return "documentation"
        if suffix in {".py", ".ps1", ".bat", ".sh"}:
            return "script"
        return "unknown"

    def _existing_allowed_roots(self, allowed_roots: list[str]) -> list[Path]:
        roots: list[Path] = []
        for name in allowed_roots:
            candidate = (self.project_root / name).resolve()
            if self._is_under_project_root(candidate) and candidate.exists() and candidate.is_dir():
                roots.append(candidate)
        return roots

    def _should_skip_path(
        self,
        path: Path,
        config: DirectoryScanConfig,
        skipped: list[dict[str, Any]],
    ) -> bool:
        relative = as_posix_relative(path, self.project_root)
        lowered_parts = [part.lower() for part in Path(relative).parts]

        if not self._is_under_project_root(path.resolve()):
            skipped.append({"path": str(path), "reason": "outside_project_root"})
            return True

        if any(part in set(config.ignored_folders) for part in lowered_parts):
            skipped.append({"path": relative, "reason": "ignored_folder"})
            return True

        if "logs" in lowered_parts and "old" in lowered_parts:
            skipped.append({"path": relative, "reason": "ignored_logs_old"})
            return True

        if path.suffix.lower() in set(config.ignored_extensions):
            skipped.append({"path": relative, "reason": "ignored_extension"})
            return True

        if self._is_secret_path(path):
            skipped.append({"path": relative, "reason": "secret_or_env_file"})
            return True

        return False

    def _metadata_for(self, path: Path, category: str, config: DirectoryScanConfig) -> dict[str, Any]:
        metadata: dict[str, Any] = {"category_reason": category}
        if path.suffix.lower() == ".py" and config.read_small_python_files and path.stat().st_size <= 64_000:
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                return metadata
            metadata["has_deprecated_import"] = any(marker in text for marker in DEPRECATED_IMPORT_MARKERS)
            metadata["line_count"] = len(text.splitlines())
        return metadata

    def _is_secret_path(self, path: Path) -> bool:
        lowered = [part.lower() for part in path.parts]
        name = path.name.lower()
        if name.startswith(".env"):
            return True
        return any(secret in part for part in lowered for secret in SECRET_NAMES if secret != ".env")

    def _is_under_project_root(self, path: Path) -> bool:
        try:
            path.relative_to(self.project_root)
            return True
        except ValueError:
            return False

    @staticmethod
    def _mtime_iso(timestamp: float) -> str:
        from datetime import UTC, datetime

        return datetime.fromtimestamp(timestamp, UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    @staticmethod
    def write_json(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
