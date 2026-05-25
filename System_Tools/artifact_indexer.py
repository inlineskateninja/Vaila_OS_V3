from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class ArtifactIndexer:
    """
    Indexes generated reports, council syntheses, scans, imported docs,
    and presentations so Vaila can reference its own work history.
    """

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.artifacts_dir = project_root / "data" / "artifacts"
        self.imports_dir = project_root / "Sandbox" / "Imported_Documents"
        self.index_file = project_root / "data" / "artifact_index.json"
        
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.imports_dir.mkdir(parents=True, exist_ok=True)

    def load_index(self) -> list[dict[str, Any]]:
        if not self.index_file.exists():
            return []
        try:
            return json.loads(self.index_file.read_text(encoding="utf-8"))
        except Exception:
            return []

    def save_index(self, index: list[dict[str, Any]]) -> bool:
        try:
            self.index_file.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
            return True
        except Exception:
            return False

    def build_index(self) -> dict[str, Any]:
        index = []
        indexed_files = 0

        # 1. Scan data/artifacts
        for p in self.artifacts_dir.glob("*.md"):
            if p.is_file():
                meta = self._parse_file_metadata(p, category="artifact")
                index.append(meta)
                indexed_files += 1

        # 2. Scan Sandbox/Imported_Documents
        for p in self.imports_dir.glob("*"):
            if p.is_file() and p.name != ".gitignore":
                meta = self._parse_file_metadata(p, category="imported_document")
                index.append(meta)
                indexed_files += 1

        self.save_index(index)
        return {
            "ok": True,
            "total_indexed": indexed_files,
            "index_path": str(self.index_file.relative_to(self.project_root))
        }

    def search_index(self, query: str, category: str | None = None) -> list[dict[str, Any]]:
        index = self.load_index()
        if not index:
            # Rebuild dynamically if index is empty to make it fully functional!
            self.build_index()
            index = self.load_index()

        query_terms = [t.lower() for t in query.split() if t]
        matches = []

        for item in index:
            if category and item.get("category") != category:
                continue

            searchable = (
                item.get("filename", "").lower() + " " +
                item.get("category", "").lower() + " " +
                " ".join(item.get("keywords", [])).lower() + " " +
                item.get("summary_snippet", "").lower()
            )

            if not query_terms or all(term in searchable for term in query_terms):
                matches.append(item)

        return matches

    def _parse_file_metadata(self, path: Path, category: str) -> dict[str, Any]:
        stat = path.stat()
        mtime = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.localtime(stat.st_mtime))
        
        keywords = []
        summary = ""

        # Auto-extract keywords and summary snippet based on file suffix
        if path.suffix.lower() == ".md":
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
                lines = content.splitlines()
                
                # First non-empty lines are summary
                summary_lines = []
                for line in lines:
                    cleaned = line.strip()
                    if cleaned and not cleaned.startswith("#"):
                        summary_lines.append(cleaned)
                        if len(summary_lines) >= 3:
                            break
                summary = " ".join(summary_lines)[:250]

                # Keyword tagging
                content_lower = content.lower()
                if "self-assessment" in content_lower or "self assessment" in content_lower:
                    keywords.append("self_assessment")
                if "synthesis" in content_lower:
                    keywords.append("synthesis")
                if "council" in content_lower:
                    keywords.append("council")
                if "audit" in content_lower:
                    keywords.append("audit")
                if "doctor" in content_lower or "diagnostics" in content_lower:
                    keywords.append("diagnostics")

            except Exception:
                pass

        # Tag category-based defaults
        if category == "imported_document":
            keywords.append("imported")
        else:
            keywords.append("report")

        # Fallback summary
        if not summary:
            summary = f"Binary or plain document of size {stat.st_size} bytes."

        return {
            "filename": path.name,
            "path": str(path.relative_to(self.project_root)),
            "category": category,
            "size_kb": f"{stat.st_size / 1024:.1f} KB",
            "modified_time": mtime,
            "keywords": keywords,
            "summary_snippet": summary
        }
