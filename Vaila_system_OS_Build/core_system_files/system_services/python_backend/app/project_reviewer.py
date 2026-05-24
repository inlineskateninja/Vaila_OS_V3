from __future__ import annotations

from pathlib import Path
from typing import Any

from app.activity_log import ActivityLog, utc_now
from app.candidate_store import CandidateStore
from app.memory_store import MemoryStore


class ProjectReviewer:
    """Creates a deterministic Phase 2 project status review.

    This review intentionally avoids using an LLM. It is a stable diagnostic layer
    the user can trust even when LM Studio is offline.
    """

    def __init__(
        self,
        project_root: str | Path,
        memory_store: MemoryStore,
        candidate_store: CandidateStore,
        activity_log: ActivityLog,
    ) -> None:
        self.project_root = Path(project_root)
        self.memory_store = memory_store
        self.candidate_store = candidate_store
        self.activity_log = activity_log

    def build_review(self, limit: int = 50) -> dict[str, Any]:
        pending = self.candidate_store.list_candidates("pending")
        approved = self.candidate_store.list_candidates("approved")
        rejected = self.candidate_store.list_candidates("rejected")
        recent_events = self.activity_log.recent(limit=limit)
        counts = self.activity_log.counts_by_type()

        risks = self._build_risks(pending_count=len(pending), counts=counts)
        next_steps = self._build_next_steps(pending_count=len(pending), counts=counts)
        tests = self._build_suggested_tests(pending_count=len(pending), counts=counts)

        return {
            "ok": True,
            "generated_at": utc_now(),
            "phase": "Phase 2: Practical assistant usefulness",
            "phase_fit": (
                "The app now has a local service, desktop client, document intake, "
                "memory candidate review, and operational logging. That keeps it inside Phase 2, "
                "not Phase 3 agent autonomy. Correct restraint."
            ),
            "state": {
                "project_root": str(self.project_root),
                "memory_records": len(self.memory_store.records),
                "pending_candidates": len(pending),
                "approved_candidates": len(approved),
                "rejected_candidates": len(rejected),
                "activity_events": len(self.activity_log.events),
                "activity_counts": counts,
            },
            "recent_activity": [event.to_dict() for event in recent_events],
            "risks": risks,
            "recommended_next_steps": next_steps,
            "suggested_tests": tests,
            "summary": self._build_summary(len(pending), len(approved), len(rejected), counts),
        }

    def _build_summary(
        self,
        pending_count: int,
        approved_count: int,
        rejected_count: int,
        counts: dict[str, int],
    ) -> str:
        imports = counts.get("document_imported", 0)
        chats = counts.get("chat_completed", 0) + counts.get("chat_failed", 0)
        return (
            f"Vaila has {len(self.memory_store.records)} memory record(s), "
            f"{pending_count} pending candidate(s), {approved_count} approved candidate(s), "
            f"and {rejected_count} rejected candidate(s). "
            f"Logged activity includes {imports} document import(s) and {chats} chat interaction(s)."
        )

    def _build_risks(self, pending_count: int, counts: dict[str, int]) -> list[str]:
        risks: list[str] = []
        if pending_count >= 10:
            risks.append("Pending memory candidates are building up. Review them before importing more files.")
        if counts.get("document_imported", 0) == 0:
            risks.append("No document imports are logged yet. The intake pipeline still needs real-world testing.")
        if counts.get("candidate_approved", 0) == 0 and counts.get("document_imported", 0) > 0:
            risks.append("Documents have been imported, but no candidates have been approved. Memory usefulness may remain low.")
        if counts.get("chat_failed", 0) > counts.get("chat_completed", 0):
            risks.append("Logged chat failures outnumber successful chat completions. Model/profile stability should be checked.")
        if not risks:
            risks.append("No major Phase 2 operational risk detected from the current logs.")
        return risks

    def _build_next_steps(self, pending_count: int, counts: dict[str, int]) -> list[str]:
        steps: list[str] = []
        if pending_count:
            steps.append("Review pending memory candidates and approve only the ones worth preserving.")
        if counts.get("document_imported", 0) < 3:
            steps.append("Import a few representative project files to test whether candidate extraction is useful enough.")
        steps.append("Run a short project review after each build session so Vaila can summarize what changed.")
        steps.append("Keep agents out of scope until logs, reviews, and approval workflows feel boringly reliable.")
        return steps

    def _build_suggested_tests(self, pending_count: int, counts: dict[str, int]) -> list[str]:
        tests = [
            "Start the service and confirm /health shows memory, candidates, and activity counts.",
            "Send one chat message through the desktop client, then verify it appears in recent activity.",
            "Import one small markdown file and confirm pending candidates appear in Candidate Review.",
            "Approve one low-risk candidate, then search memory for a term from that candidate.",
            "Run Project Review and confirm the report reflects the import, approval, and chat events.",
        ]
        if pending_count:
            tests.append("Reject one weak candidate with a note and confirm it moves to rejected status.")
        return tests
