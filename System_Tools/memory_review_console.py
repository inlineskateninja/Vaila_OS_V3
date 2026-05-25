from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from uuid import uuid4


class MemoryReviewConsole:
    """
    Lets the user approve, edit, reject, tag, search, and promote memory candidates
    into durable memory.
    """

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.candidates_file = project_root / "data" / "openbrain_memory_candidates.jsonl"
        self.durable_file = project_root / "data" / "openbrain_durable_memories.jsonl"

    def list_reviewable_candidates(self) -> list[dict[str, Any]]:
        if not self.candidates_file.exists():
            return []
        
        candidates = []
        try:
            lines = self.candidates_file.read_text(encoding="utf-8").splitlines()
            for line in lines:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    # Filter candidates that are logged and need review
                    if isinstance(record, dict) and record.get("status") in {"needs_user_review", "candidate_logged"}:
                        candidates.append(record)
                except Exception:
                    continue
        except Exception:
            pass
        return candidates

    def edit_candidate_payload(self, cand_id: str, new_text: str) -> bool:
        if not self.candidates_file.exists():
            return False

        updated_records = []
        found = False
        try:
            lines = self.candidates_file.read_text(encoding="utf-8").splitlines()
            for line in lines:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    if record.get("candidate_id") == cand_id:
                        if "payload" in record and isinstance(record["payload"], dict):
                            record["payload"]["text"] = new_text
                        found = True
                    updated_records.append(record)
                except Exception:
                    updated_records.append(record)
            
            # Write back
            with self.candidates_file.open("w", encoding="utf-8") as f:
                for r in updated_records:
                    f.write(json.dumps(r) + "\n")
            return found
        except Exception:
            return False

    def reject_candidate(self, cand_id: str) -> bool:
        if not self.candidates_file.exists():
            return False

        updated_records = []
        found = False
        try:
            lines = self.candidates_file.read_text(encoding="utf-8").splitlines()
            for line in lines:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    if record.get("candidate_id") == cand_id:
                        record["status"] = "rejected"
                        found = True
                    updated_records.append(record)
                except Exception:
                    updated_records.append(record)

            with self.candidates_file.open("w", encoding="utf-8") as f:
                for r in updated_records:
                    f.write(json.dumps(r) + "\n")
            return found
        except Exception:
            return False

    def promote_candidate(self, cand_id: str, category: str = "general", project_only: bool = False, custom_text: str | None = None) -> dict[str, Any]:
        candidates = self.list_reviewable_candidates()
        target_cand = None
        for cand in candidates:
            if cand.get("candidate_id") == cand_id:
                target_cand = cand
                break

        if not target_cand:
            return {"ok": False, "error": f"Candidate with ID '{cand_id}' not found or is already reviewed."}

        text = custom_text if custom_text is not None else target_cand.get("payload", {}).get("text", "")
        if not text:
            return {"ok": False, "error": "No memory text found to promote."}

        # Promote to Durable Memory
        self.durable_file.parent.mkdir(parents=True, exist_ok=True)
        durable_record = {
            "memory_id": f"dur_{uuid4().hex}",
            "approved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "text": text,
            "category": category,
            "project_only": project_only,
            "original_candidate_id": cand_id,
            "source": target_cand.get("payload", {}).get("source", "openbrain")
        }

        try:
            with self.durable_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(durable_record) + "\n")
            
            # Mark candidate as approved
            self.reject_candidate(cand_id)  # Reject/archives the queue entry by changing its status so it's filtered out
            
            # Also update candidate status explicitly to 'approved'
            updated_records = []
            lines = self.candidates_file.read_text(encoding="utf-8").splitlines()
            for line in lines:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    if record.get("candidate_id") == cand_id:
                        record["status"] = "approved"
                    updated_records.append(record)
                except Exception:
                    updated_records.append(record)
            
            with self.candidates_file.open("w", encoding="utf-8") as f:
                for r in updated_records:
                    f.write(json.dumps(r) + "\n")

            return {"ok": True, "memory_id": durable_record["memory_id"], "memory": durable_record}
        except Exception as exc:
            return {"ok": False, "error": f"Failed to promote candidate: {exc}"}

    def search_durable_memories(self, query: str, category: str | None = None) -> list[dict[str, Any]]:
        if not self.durable_file.exists():
            return []

        matches = []
        query_terms = [term for term in query.lower().split() if term]
        try:
            lines = self.durable_file.read_text(encoding="utf-8").splitlines()
            for line in lines:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    if not isinstance(record, dict):
                        continue
                    if category and record.get("category") != category:
                        continue
                    
                    searchable = record.get("text", "").lower()
                    if not query_terms or all(term in searchable for term in query_terms):
                        matches.append(record)
                except Exception:
                    continue
        except Exception:
            pass
        return matches
