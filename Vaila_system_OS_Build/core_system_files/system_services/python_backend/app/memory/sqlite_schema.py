import sqlite3


def create_tables(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()

    # 1. memory_items
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memory_items (
            id TEXT PRIMARY KEY,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            category TEXT,
            confidence TEXT,
            source_type TEXT,
            source_document_id TEXT,
            source_path TEXT,
            created_at TEXT,
            last_updated TEXT,
            approved_at TEXT,
            review_status TEXT,
            sensitivity TEXT,
            memory_type TEXT,
            expires_at TEXT,
            source_event_id TEXT,
            created_by TEXT,
            relevance_score REAL,
            last_recalled_at TEXT,
            recall_count INTEGER,
            raw_json TEXT NOT NULL
        )
    """)

    # 2. memory_tags
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memory_tags (
            memory_id TEXT,
            tag TEXT,
            PRIMARY KEY (memory_id, tag),
            FOREIGN KEY (memory_id) REFERENCES memory_items (id) ON DELETE CASCADE
        )
    """)

    # 3. memory_persona_scope
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memory_persona_scope (
            memory_id TEXT,
            persona TEXT,
            PRIMARY KEY (memory_id, persona),
            FOREIGN KEY (memory_id) REFERENCES memory_items (id) ON DELETE CASCADE
        )
    """)

    # 4. memory_candidates
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memory_candidates (
            id TEXT PRIMARY KEY,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            status TEXT,
            category TEXT,
            confidence TEXT,
            source_type TEXT,
            source_document_id TEXT,
            source_path TEXT,
            source_title TEXT,
            created_at TEXT,
            reviewed_at TEXT,
            review_note TEXT,
            sensitivity TEXT,
            memory_type TEXT,
            source_event_id TEXT,
            proposed_by TEXT,
            requires_user_approval INTEGER,
            relevance_score REAL,
            raw_json TEXT NOT NULL
        )
    """)

    # 5. memory_candidate_tags
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memory_candidate_tags (
            candidate_id TEXT,
            tag TEXT,
            PRIMARY KEY (candidate_id, tag),
            FOREIGN KEY (candidate_id) REFERENCES memory_candidates (id) ON DELETE CASCADE
        )
    """)

    # 6. memory_candidate_persona_scope
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memory_candidate_persona_scope (
            candidate_id TEXT,
            persona TEXT,
            PRIMARY KEY (candidate_id, persona),
            FOREIGN KEY (candidate_id) REFERENCES memory_candidates (id) ON DELETE CASCADE
        )
    """)

    # 7. memory_candidate_chunks
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memory_candidate_chunks (
            candidate_id TEXT,
            chunk_id TEXT,
            PRIMARY KEY (candidate_id, chunk_id),
            FOREIGN KEY (candidate_id) REFERENCES memory_candidates (id) ON DELETE CASCADE
        )
    """)

    # 8. memory_recall_events
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memory_recall_events (
            id TEXT PRIMARY KEY,
            created_at TEXT,
            request_id TEXT,
            persona TEXT,
            task_type TEXT,
            query TEXT,
            memory_ids_json TEXT,
            scores_json TEXT,
            filters_json TEXT,
            used_in_context INTEGER,
            source TEXT,
            notes TEXT,
            raw_json TEXT NOT NULL
        )
    """)

    conn.commit()
