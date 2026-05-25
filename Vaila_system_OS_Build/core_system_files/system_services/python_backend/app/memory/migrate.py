import json
import sqlite3
from pathlib import Path
from typing import Any

from app.paths import get_vaila_paths
from app.memory.config import load_memory_config
from app.memory.jsonl_backend import JsonlMemoryBackend
from app.memory.sqlite_backend import SQLiteMemoryBackend
from app.memory.sqlite_schema import create_tables

def migrate_jsonl_to_sqlite(project_root: str | Path, sqlite_path: str | Path | None = None, dry_run: bool = True) -> dict[str, Any]:
    summary = {
        "dry_run": dry_run,
        "memory_records_found": 0,
        "memory_records_inserted": 0,
        "candidates_found": 0,
        "candidates_inserted": 0,
        "skipped_duplicates": 0,
        "errors": []
    }

    try:
        project_root = Path(project_root)
        paths = get_vaila_paths(project_root)

        # 1. Resolve SQLite DB Path
        if sqlite_path is None:
            config = load_memory_config(project_root)
            sqlite_path_str = config.get("sqlite_path", "data/vaila_memory.sqlite3")
            sqlite_path = Path(sqlite_path_str)
            if not sqlite_path.is_absolute():
                sqlite_path = project_root / sqlite_path
        else:
            sqlite_path = Path(sqlite_path)

        # 2. Load JSONL Backend
        jsonl_backend = JsonlMemoryBackend(paths.memory_root, paths.candidate_root)
        jsonl_backend.load()

        records = jsonl_backend.memory_store.records
        candidates = jsonl_backend.list_candidates("all")

        summary["memory_records_found"] = len(records)
        summary["candidates_found"] = len(candidates)

        # Identify duplicates first by opening the connection
        existing_record_ids = set()
        existing_candidate_ids = set()
        
        if sqlite_path.exists():
            conn = sqlite3.connect(sqlite_path)
            try:
                create_tables(conn)
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM memory_items")
                existing_record_ids = {row[0] for row in cursor.fetchall()}
                cursor.execute("SELECT id FROM memory_candidates")
                existing_candidate_ids = {row[0] for row in cursor.fetchall()}
            except Exception:
                pass
            finally:
                conn.close()

        if dry_run:
            for record in records:
                if record.id in existing_record_ids:
                    summary["skipped_duplicates"] += 1
                else:
                    summary["memory_records_inserted"] += 1

            for candidate in candidates:
                if candidate.id in existing_candidate_ids:
                    summary["skipped_duplicates"] += 1
                else:
                    summary["candidates_inserted"] += 1

            return summary

        # Real Run: Write to SQLite
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        sqlite_backend = SQLiteMemoryBackend(sqlite_path)
        sqlite_backend.load()

        try:
            cursor = sqlite_backend.conn.cursor()

            # Copy memory records
            for record in records:
                try:
                    if record.id in existing_record_ids:
                        summary["skipped_duplicates"] += 1
                        continue

                    # Insert record using sqlite_backend.append_memory
                    sqlite_backend.append_memory(record)
                    summary["memory_records_inserted"] += 1
                except Exception as rec_err:
                    summary["errors"].append(f"Record {record.id} copy failed: {str(rec_err)}")

            # Copy memory candidates
            for candidate in candidates:
                try:
                    if candidate.id in existing_candidate_ids:
                        summary["skipped_duplicates"] += 1
                        continue

                    raw_json = json.dumps(candidate.to_dict(), ensure_ascii=False)
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

                    summary["candidates_inserted"] += 1
                except Exception as cand_err:
                    summary["errors"].append(f"Candidate {candidate.id} copy failed: {str(cand_err)}")

            sqlite_backend.conn.commit()

        finally:
            sqlite_backend.close()

    except Exception as glob_err:
        summary["errors"].append(f"Global migration failed: {str(glob_err)}")

    return summary
