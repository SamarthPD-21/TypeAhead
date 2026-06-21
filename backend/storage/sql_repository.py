import sqlite3
import os
from backend.models.query_data import SearchQueryRecord

class SQLiteDatabaseStorage:
    """Wrapper around SQLite database with WAL journaling for durable, high-throughput batch writes."""
    
    def __init__(self, db_file_path: str):
        self.db_file_path = db_file_path

    def _acquire_conn(self) -> sqlite3.Connection:
        """Helper to open a connection to the SQLite database file."""
        return sqlite3.connect(self.db_file_path)

    def initialize_tables(self) -> None:
        """Initializes the database schema with index for prefix matching."""
        with self._acquire_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS search_terms_directory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    phrase TEXT NOT NULL UNIQUE,
                    hits_count INTEGER NOT NULL DEFAULT 1,
                    activity_score REAL NOT NULL DEFAULT 0.0,
                    updated_at INTEGER NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_search_phrase
                ON search_terms_directory(phrase);
            """)

    def fetch_term(self, phrase: str) -> SearchQueryRecord | None:
        """Retrieves a single query record from the database."""
        with self._acquire_conn() as conn:
            cursor = conn.execute(
                "SELECT phrase, hits_count, activity_score, updated_at FROM search_terms_directory WHERE phrase = ?",
                (phrase,)
            )
            row = cursor.fetchone()
            if row:
                return SearchQueryRecord(phrase=row[0], hits_count=row[1], activity_score=row[2], updated_at=row[3])
        return None

    def query_by_prefix(self, prefix: str, max_results: int = 100) -> list[SearchQueryRecord]:
        """Fetches all records matching a prefix query (using LIKE 'prefix%')."""
        with self._acquire_conn() as conn:
            cursor = conn.execute(
                """
                SELECT phrase, hits_count, activity_score, updated_at
                FROM search_terms_directory
                WHERE phrase LIKE ?
                LIMIT ?
                """,
                (f"{prefix}%", max_results)
            )
            rows = cursor.fetchall()
        return [
            SearchQueryRecord(phrase=row[0], hits_count=row[1], activity_score=row[2], updated_at=row[3])
            for row in rows
        ]

    def fetch_trending_terms(self, limit: int = 100) -> list[SearchQueryRecord]:
        """Gets globally trending search phrases sorted by decay score and total hits."""
        with self._acquire_conn() as conn:
            cursor = conn.execute(
                """
                SELECT phrase, hits_count, activity_score, updated_at
                FROM search_terms_directory
                ORDER BY activity_score DESC, hits_count DESC, phrase ASC
                LIMIT ?
                """,
                (limit,)
            )
            rows = cursor.fetchall()
        return [
            SearchQueryRecord(phrase=row[0], hits_count=row[1], activity_score=row[2], updated_at=row[3])
            for row in rows
        ]

    def fetch_scores_for_batch(self, phrases: list[str]) -> dict[str, tuple[float, int]]:
        """Retrieves existing scores and timestamps for a batch of search terms."""
        if not phrases:
            return {}

        accumulated_results = {}
        chunk_size = 900
        with self._acquire_conn() as conn:
            for idx in range(0, len(phrases), chunk_size):
                chunk = phrases[idx:idx + chunk_size]
                binds = ",".join(["?"] * len(chunk))
                cursor = conn.execute(
                    f"SELECT phrase, activity_score, updated_at FROM search_terms_directory WHERE phrase IN ({binds})",
                    chunk
                )
                for row in cursor.fetchall():
                    accumulated_results[row[0]] = (row[1], row[2])
        return accumulated_results

    def upsert_records_batch(self, batch_data: list[tuple[str, int, float, int]]) -> None:
        """Executes a single batch SQLite transaction to upsert multiple search term records."""
        if not batch_data:
            return
            
        with self._acquire_conn() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executemany(
                """
                INSERT INTO search_terms_directory (phrase, hits_count, activity_score, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(phrase)
                DO UPDATE SET
                    hits_count = search_terms_directory.hits_count + excluded.hits_count,
                    activity_score = excluded.activity_score,
                    updated_at = excluded.updated_at
                """,
                batch_data
            )
