from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


class PatchExporter:
    """
    Writes proposed changes into Sandbox/Proposed_Patches.

    It does not apply patches automatically.
    """

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.patch_dir = project_root / "Sandbox" / "Proposed_Patches"
        self.patch_dir.mkdir(parents=True, exist_ok=True)

    def export_patch(self, filename_hint: str, content: str) -> Path:
        safe_hint = "".join(
            char if char.isalnum() or char in {"_", "-", "."} else "_"
            for char in filename_hint
        )

        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = self.patch_dir / f"{stamp}_{safe_hint}"
        path.write_text(content, encoding="utf-8")
        return path
