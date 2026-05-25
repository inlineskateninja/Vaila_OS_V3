import json
import sqlite3
from pathlib import Path
from typing import Any
from datetime import datetime, timezone

from app.memory.backend import MemoryBackend
from app.memory.models import MemoryRecord, MemoryCandidate
from app.memory.sqlite_schema import create_tables
from app.memory_store import normalize_words, depreciation_score, recency_bucket


class SQLiteMemoryBackend(MemoryBackend):
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.conn: sqlite3.Connection | None = None

    def load(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False allows FastAPI multi-threaded access safely
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.execute("PRAGMA foreign_keys = ON")
        create_tables(self.conn)

    def close(self) -> None:
        if self.conn:
            self.conn.close()
            self.conn = None

    def state_summary(self) -> dict:
        cursor = self.conn.cursor()

        # 1. Total records
        cursor.execute("SELECT COUNT(*) FROM memory_items")
        records_count = cursor.fetchone()[0]

        # 2. Categories count
        cursor.execute("SELECT category, COUNT(*) FROM memory_items GROUP BY category")
        categories = dict(cursor.fetchall())

        # 3. Recency bucket count
        cursor.execute("SELECT raw_json FROM memory_items")
        rows = cursor.fetchall()
        recency: dict[str, int] = {}
        for row in rows:
            record = MemoryRecord.from_dict(json.loads(row[0]))
            bucket = recency_bucket(record)
            recency[bucket] = recency.get(bucket, 0) + 1

        # 4. Candidates counts
        cursor.execute("SELECT status, COUNT(*) FROM memory_candidates GROUP BY status")
        candidates = dict(cursor.fetchall())

        return {
            "memory_records": records_count,
            "memory_categories": dict(sorted(categories.items())),
            "memory_recency": dict(sorted(recency.items())),
            "pending_candidates": candidates.get("pending", 0),
            "approved_candidates": candidates.get("approved", 0),
            "rejected_candidates": candidates.get("rejected", 0),
        }

    def create_candidate(self, candidate: MemoryCandidate) -> MemoryCandidate:
        self.create_candidates([candidate])
        return candidate

    def create_candidates(self, candidates: list[MemoryCandidate]) -> list[MemoryCandidate]:
        cursor = self.conn.cursor()
        added: list[MemoryCandidate] = []

        for candidate in candidates:
            # Check duplicates
            cursor.execute("SELECT COUNT(*) FROM memory_candidates WHERE id = ?", (candidate.id,))
            if cursor.fetchone()[0] > 0:
                continue

            candidate.status = "pending"
            raw_json = json.dumps(candidate.to_dict(), ensure_ascii=False)

            # Insert Candidate
            cursor.execute(
                """
                INSERT INTO memory_candidates (
                    id, question, answer, status, category, confidence, source_type,
                    source_document_id, source_path, source_title, created_at,
                    reviewed_at, review_note, sensitivity, memory_type,
                    source_event_id, proposed_by, requires_user_approval,
                    relevance_score, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    candidate.id,
                    candidate.question,
                    candidate.answer,
                    candidate.status,
                    candidate.category,
                    candidate.confidence,
                    candidate.source_type,
                    candidate.source_document_id,
                    candidate.source_path,
                    candidate.source_title,
                    candidate.created_at,
                    candidate.reviewed_at,
                    candidate.review_note,
                    candidate.sensitivity,
                    candidate.memory_type,
                    candidate.source_event_id,
                    candidate.proposed_by,
                    1 if candidate.requires_user_approval else 0,
                    candidate.relevance_score,
                    raw_json,
                ),
            )

            # Insert Candidate Tags
            for tag in candidate.tags:
                cursor.execute(
                    "INSERT OR IGNORE INTO memory_candidate_tags (candidate_id, tag) VALUES (?, ?)",
                    (candidate.id, tag),
                )

            # Insert Candidate Persona Scope
            for persona in candidate.persona_scope:
                cursor.execute(
                    "INSERT OR IGNORE INTO memory_candidate_persona_scope (candidate_id, persona) VALUES (?, ?)",
                    (candidate.id, persona),
                )

            # Insert Candidate Chunks
            for chunk_id in candidate.chunk_ids:
                cursor.execute(
                    "INSERT OR IGNORE INTO memory_candidate_chunks (candidate_id, chunk_id) VALUES (?, ?)",
                    (candidate.id, chunk_id),
                )

            added.append(candidate)

        self.conn.commit()
        return added

    def list_candidates(self, status: str = "pending") -> list[MemoryCandidate]:
        cursor = self.conn.cursor()
        if status == "all":
            cursor.execute("SELECT raw_json FROM memory_candidates")
        else:
            cursor.execute("SELECT raw_json FROM memory_candidates WHERE status = ?", (status,))
        rows = cursor.fetchall()
        return [MemoryCandidate.from_dict(json.loads(row[0])) for row in rows]

    def get_candidate(self, candidate_id: str) -> MemoryCandidate | None:
        cursor = self.conn.cursor()
        cursor.execute("SELECT raw_json FROM memory_candidates WHERE id = ?", (candidate_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return MemoryCandidate.from_dict(json.loads(row[0]))

    def approve_candidate(self, candidate_id: str) -> tuple[MemoryCandidate, Any]:
        candidate = self.get_candidate(candidate_id)
        if candidate is None:
            raise KeyError(f"Unknown candidate: {candidate_id}")
        if candidate.status != "pending":
            raise ValueError(f"Candidate is not pending: {candidate_id} ({candidate.status})")

        reviewed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        record = candidate.to_memory_record(approved_at=reviewed_at)

        # Direct database transaction
        cursor = self.conn.cursor()

        # 1. Write approved MemoryRecord
        raw_json_record = json.dumps(record.to_dict(), ensure_ascii=False)
        cursor.execute(
            """
            INSERT OR REPLACE INTO memory_items (
                id, question, answer, category, confidence, source_type,
                source_document_id, source_path, created_at, last_updated,
                approved_at, review_status, sensitivity, memory_type,
                expires_at, source_event_id, created_by, relevance_score,
                last_recalled_at, recall_count, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                record.id,
                record.question,
                record.answer,
                record.category,
                record.confidence,
                record.source_type,
                record.source_document_id,
                record.source_path,
                record.created_at,
                record.last_updated,
                record.approved_at,
                record.review_status,
                record.sensitivity,
                record.memory_type,
                record.expires_at,
                record.source_event_id,
                record.created_by,
                record.relevance_score,
                record.last_recalled_at,
                record.recall_count,
                raw_json_record,
            ),
        )

        for tag in record.tags:
            cursor.execute(
                "INSERT OR IGNORE INTO memory_tags (memory_id, tag) VALUES (?, ?)",
                (record.id, tag),
            )

        for persona in record.persona_scope:
            cursor.execute(
                "INSERT OR IGNORE INTO memory_persona_scope (memory_id, persona) VALUES (?, ?)",
                (record.id, persona),
            )

        # 2. Update candidate status to approved in memory_candidates
        candidate.status = "approved"
        candidate.reviewed_at = reviewed_at
        raw_json_cand = json.dumps(candidate.to_dict(), ensure_ascii=False)
        cursor.execute(
            "UPDATE memory_candidates SET status = 'approved', reviewed_at = ?, raw_json = ? WHERE id = ?",
            (reviewed_at, raw_json_cand, candidate_id),
        )

        self.conn.commit()
        # Return candidate and virtual written path path (we return DB path)
        return candidate, self.db_path

    def reject_candidate(self, candidate_id: str, note: str = "") -> MemoryCandidate:
        candidate = self.get_candidate(candidate_id)
        if candidate is None:
            raise KeyError(f"Unknown candidate: {candidate_id}")
        if candidate.status != "pending":
            raise ValueError(f"Candidate is not pending: {candidate_id} ({candidate.status})")

        reviewed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        candidate.status = "rejected"
        candidate.reviewed_at = reviewed_at
        candidate.review_note = note

        cursor = self.conn.cursor()
        raw_json = json.dumps(candidate.to_dict(), ensure_ascii=False)
        cursor.execute(
            "UPDATE memory_candidates SET status = 'rejected', reviewed_at = ?, review_note = ?, raw_json = ? WHERE id = ?",
            (reviewed_at, note, raw_json, candidate_id),
        )
        self.conn.commit()
        return candidate

    def search_memory(
        self,
        query: str,
        persona: str = "proto_jane",
        tags: list[str] | None = None,
        limit: int = 8,
        category: str | None = None,
    ) -> list[MemoryRecord]:
        return [record for score, record in self.search_memory_scored(query, persona, tags, limit, category)]

    def search_memory_scored(
        self,
        query: str,
        persona: str = "proto_jane",
        tags: list[str] | None = None,
        limit: int = 8,
        category: str | None = None,
    ) -> list[tuple[float, MemoryRecord]]:
        tags = tags or []
        query_words = normalize_words(query)
        tag_set = set(tags)

        cursor = self.conn.cursor()
        cursor.execute("SELECT raw_json FROM memory_items")
        rows = cursor.fetchall()
        records = [MemoryRecord.from_dict(json.loads(row[0])) for row in rows]

        scored: list[tuple[float, MemoryRecord]] = []
        for record in records:
            if category and record.category != category:
                continue
            score = 0.0

            memory_text = f"{record.question} {record.answer} {' '.join(record.tags)} {record.category}"
            memory_words = normalize_words(memory_text)

            overlap = query_words.intersection(memory_words)
            score += len(overlap) * 2

            record_tags = set(record.tags)
            tag_overlap = tag_set.intersection(record_tags)
            score += len(tag_overlap) * 4

            scope = set(record.persona_scope)
            if "all" in scope:
                score += 2
            if persona in scope:
                score += 4

            if record.confidence == "high":
                score += 1

            score += depreciation_score(record)
            score *= max(record.relevance_score, 0.1)

            if score > 0:
                scored.append((score, record))

        scored.sort(key=lambda item: item[0], reverse=True)
        return scored[:limit]

    def append_memory(self, record: MemoryRecord, relative_path: str | None = None) -> Any:
        cursor = self.conn.cursor()
        if not record.last_updated:
            record.last_updated = datetime.now(timezone.utc).date().isoformat()
        if not record.created_at:
            record.created_at = record.last_updated

        raw_json_record = json.dumps(record.to_dict(), ensure_ascii=False)
        cursor.execute(
            """
            INSERT OR REPLACE INTO memory_items (
                id, question, answer, category, confidence, source_type,
                source_document_id, source_path, created_at, last_updated,
                approved_at, review_status, sensitivity, memory_type,
                expires_at, source_event_id, created_by, relevance_score,
                last_recalled_at, recall_count, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                record.id,
                record.question,
                record.answer,
                record.category,
                record.confidence,
                record.source_type,
                record.source_document_id,
                record.source_path,
                record.created_at,
                record.last_updated,
                record.approved_at,
                record.review_status,
                record.sensitivity,
                record.memory_type,
                record.expires_at,
                record.source_event_id,
                record.created_by,
                record.relevance_score,
                record.last_recalled_at,
                record.recall_count,
                raw_json_record,
            ),
        )

        for tag in record.tags:
            cursor.execute(
                "INSERT OR IGNORE INTO memory_tags (memory_id, tag) VALUES (?, ?)",
                (record.id, tag),
            )

        for persona in record.persona_scope:
            cursor.execute(
                "INSERT OR IGNORE INTO memory_persona_scope (memory_id, persona) VALUES (?, ?)",
                (record.id, persona),
            )

        self.conn.commit()
        return self.db_path
