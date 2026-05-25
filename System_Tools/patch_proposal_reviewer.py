from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Any


class PatchProposalReviewer:
    """
    Reads sandboxed patch exports, explains risks, groups related changes,
    and asks for approval before anything touches core files.
    """

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.patch_dir = project_root / "Sandbox" / "Proposed_Patches"
        self.backup_dir = project_root / "Sandbox" / "Backups"
        self.patch_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def list_patches(self) -> list[dict[str, Any]]:
        patches = []
        for p in self.patch_dir.glob("*"):
            if p.is_file():
                stat = p.stat()
                patches.append({
                    "filename": p.name,
                    "size_bytes": stat.st_size,
                    "mtime": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.localtime(stat.st_mtime)),
                    "path": str(p)
                })
        # Sort by mtime descending
        patches.sort(key=lambda x: x["mtime"], reverse=True)
        return patches

    def review_patch(self, filename: str) -> dict[str, Any]:
        patch_path = self.patch_dir / filename
        if not patch_path.exists():
            return {"ok": False, "error": f"Patch '{filename}' not found."}

        try:
            content = patch_path.read_text(encoding="utf-8")
        except Exception as exc:
            return {"ok": False, "error": f"Failed to read patch content: {exc}"}

        lines = content.splitlines()
        
        # Analyze target file references
        target_files = []
        for line in lines[:25]:  # Scan top header lines
            if line.startswith("# Target File:") or line.startswith("// Target File:"):
                target = line.split(":", 1)[1].strip()
                target_files.append(target)

        # Fallback target file parsing if no header is present
        if not target_files:
            # Check if filename contains hints, e.g. "20260525_120000_patch_exporter.py"
            # Target becomes System_Tools/patch_exporter.py or similar
            parts = filename.split("_", 2)
            if len(parts) >= 3:
                hint = parts[2]
                # Search project for similar file
                for p in self.project_root.rglob(hint):
                    if p.is_file() and "__pycache__" not in str(p) and ".git" not in str(p):
                        target_files.append(str(p.relative_to(self.project_root)))
                        break

        # Group related changes
        risks = []
        structural_impact = "low"
        
        for tf in target_files:
            if "Core_System_Files" in tf or "api" in tf or "cli" in tf:
                risks.append(f"Modifies Core System Gateway: Modifying '{tf}' could break API routing, startup, or client interfaces.")
                structural_impact = "critical"
            elif "System_Services" in tf:
                risks.append(f"Modifies Orchestrator or Service layer: Modifying '{tf}' impacts system orchestration or database routing.")
                structural_impact = "high"
            elif "System_Dogma" in tf:
                risks.append(f"Modifies System Dogma: Modifying core rules in '{tf}' impacts Vaila's behavior boundaries and safety.")
                structural_impact = "critical"

        # Check for dangerous code additions
        danger_triggers = [
            ("os.remove", "Contains file deletions (os.remove)."),
            ("shutil.rmtree", "Contains directory tree deletions (shutil.rmtree)."),
            ("subprocess.Popen", "Executes arbitrary subshell commands."),
            ("eval(", "Executes arbitrary dynamically parsed text evaluation."),
            ("exec(", "Contains exec() python block execution.")
        ]

        for trigger, msg in danger_triggers:
            if any(trigger in line for line in lines):
                risks.append(f"Security Alert: {msg}")
                structural_impact = "critical"

        if not risks:
            risks.append("No critical structural modifications or unsafe operations detected. Standard patch.")

        return {
            "ok": True,
            "filename": filename,
            "target_files_detected": target_files,
            "structural_impact_level": structural_impact,
            "risks_identified": risks,
            "lines_count": len(lines),
            "preview_lines": lines[:30]
        }

    def apply_patch(self, filename: str) -> dict[str, Any]:
        review = self.review_patch(filename)
        if not review.get("ok"):
            return review

        targets = review.get("target_files_detected", [])
        if not targets:
            return {"ok": False, "error": "Could not determine target files to apply this patch to."}

        patch_path = self.patch_dir / filename
        backup_files = []
        copied_files = []

        try:
            for target_rel in targets:
                target_path = self.project_root / target_rel
                
                # 1. Create a safe backup first
                if target_path.exists():
                    stamp = time.strftime("%Y%m%d_%H%M%S")
                    backup_name = f"{stamp}_backup_{target_path.name}"
                    backup_path = self.backup_dir / backup_name
                    shutil.copy2(target_path, backup_path)
                    backup_files.append(str(backup_path.relative_to(self.project_root)))

                # 2. Deploy patch to target (copies sandboxed code to core)
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(patch_path, target_path)
                copied_files.append(str(target_path.relative_to(self.project_root)))

            # Mark patch as applied (archived to Sandbox/Applied_Patches)
            applied_dir = self.project_root / "Sandbox" / "Applied_Patches"
            applied_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(patch_path, applied_dir / filename)

            return {
                "ok": True,
                "status": "applied",
                "backups_created": backup_files,
                "targets_overwritten": copied_files
            }
        except Exception as exc:
            return {"ok": False, "error": f"Failed during patch application: {exc}"}

    def render_review_report(self, filename: str) -> str:
        res = self.review_patch(filename)
        if not res.get("ok"):
            return f"❌ Review Error: {res.get('error')}"

        impact = res["structural_impact_level"].upper()
        impact_symbol = "🔴" if impact == "CRITICAL" else ("🟡" if impact == "HIGH" else "🟢")

        report = [
            f"# Patch Review Report for `{filename}`",
            f"Impact Level: {impact_symbol} **{impact}**",
            f"Lines Count: {res['lines_count']}",
            "",
            "## Target Files Impacted",
        ]
        for t in res["target_files_detected"]:
            report.append(f"- `[Target]` `{t}`")
        if not res["target_files_detected"]:
            report.append("- No target files explicitly identified.")

        report.append("")
        report.append("## 🛡️ Risk & Security Assessment")
        for r in res["risks_identified"]:
            report.append(f"- {r}")

        report.append("")
        report.append("## 📝 Code Preview")
        report.append("```python")
        for line in res["preview_lines"]:
            report.append(line)
        if res["lines_count"] > len(res["preview_lines"]):
            report.append("... [truncated] ...")
        report.append("```")

        return "\n".join(report)
