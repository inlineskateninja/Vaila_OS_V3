from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path


class DocumentImporter:
    """
    Phase 1 document importer.

    Imports documents into Sandbox for review.
    Do not write directly into long-term memory yet.
    """

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.import_dir = project_root / "Sandbox" / "Imported_Documents"
        self.import_dir.mkdir(parents=True, exist_ok=True)

    def import_document(self, source_path: str) -> str:
        source = Path(source_path)
        if not source.exists() or not source.is_file():
            return f"Source document not found: {source_path}"

        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        destination = self.import_dir / f"{stamp}_{source.name}"
        shutil.copy2(source, destination)

        return f"Imported document to sandbox: {destination}"
