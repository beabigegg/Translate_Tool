"""SQLite-based translation cache with LRU eviction."""

from __future__ import annotations

import os
import sqlite3
import threading
from pathlib import Path
from typing import Dict, Optional

from app.backend.config import CACHE_CLEANUP_BATCH, CACHE_MAX_ENTRIES
from app.backend.utils.logging_utils import logger


class TranslationCache:
    """Thread-safe translation cache with LRU eviction and size limits."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = str(db_path)
        self._lock = threading.Lock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            # Check if table exists and has the new columns
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='translations'")
            table_exists = cur.fetchone() is not None

            if not table_exists:
                # Create new table with timestamp columns
                cur.execute(
                    """
                    CREATE TABLE translations(
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        src TEXT NOT NULL,
                        tgt TEXT NOT NULL,
                        text TEXT NOT NULL,
                        result TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE (src, tgt, text)
                    )
                    """
                )
                cur.execute("CREATE INDEX IF NOT EXISTS idx_last_used ON translations(last_used_at)")
            else:
                # Migrate existing table: add columns if missing
                cur.execute("PRAGMA table_info(translations)")
                columns = {row[1] for row in cur.fetchall()}

                if "created_at" not in columns:
                    cur.execute("ALTER TABLE translations ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                    logger.info("Added created_at column to translations table")

                if "last_used_at" not in columns:
                    cur.execute("ALTER TABLE translations ADD COLUMN last_used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                    logger.info("Added last_used_at column to translations table")

                if "id" not in columns:
                    # Old schema without id, need to recreate
                    cur.execute("ALTER TABLE translations RENAME TO translations_old")
                    cur.execute(
                        """
                        CREATE TABLE translations(
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            src TEXT NOT NULL,
                            tgt TEXT NOT NULL,
                            text TEXT NOT NULL,
                            result TEXT NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            last_used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            UNIQUE (src, tgt, text)
                        )
                        """
                    )
                    cur.execute(
                        """
                        INSERT INTO translations (src, tgt, text, result)
                        SELECT src, tgt, text, result FROM translations_old
                        """
                    )
                    cur.execute("DROP TABLE translations_old")
                    logger.info("Migrated translations table to new schema")

                cur.execute("CREATE INDEX IF NOT EXISTS idx_last_used ON translations(last_used_at)")

            conn.commit()
        finally:
            conn.close()

    def get(self, src: str, tgt: str, text: str) -> Optional[str]:
        """Get cached translation and update last_used_at for LRU tracking."""
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT result FROM translations WHERE src=? AND tgt=? AND text=?",
                (src, tgt, text),
            )
            row = cur.fetchone()
            if row:
                # Update last_used_at for LRU tracking
                cur.execute(
                    "UPDATE translations SET last_used_at=CURRENT_TIMESTAMP WHERE src=? AND tgt=? AND text=?",
                    (src, tgt, text),
                )
                conn.commit()
                return row[0]
            return None
        finally:
            conn.close()

    def put(self, src: str, tgt: str, text: str, result: str) -> None:
        """Cache a translation and cleanup if exceeding limits."""
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO translations (src, tgt, text, result, created_at, last_used_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(src, tgt, text) DO UPDATE SET
                    result=excluded.result,
                    last_used_at=CURRENT_TIMESTAMP
                """,
                (src, tgt, text, result),
            )
            conn.commit()
        finally:
            conn.close()

        # Check and cleanup if needed (outside connection to avoid long locks)
        self._cleanup_if_needed()

    def _get_entry_count(self) -> int:
        """Get total number of cached entries."""
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM translations")
            return cur.fetchone()[0]
        finally:
            conn.close()

    def _cleanup_if_needed(self) -> None:
        """Remove oldest entries if cache exceeds size limit."""
        with self._lock:
            count = self._get_entry_count()
            if count <= CACHE_MAX_ENTRIES:
                return

            entries_to_remove = min(CACHE_CLEANUP_BATCH, count - CACHE_MAX_ENTRIES + CACHE_CLEANUP_BATCH)
            conn = self._get_connection()
            try:
                cur = conn.cursor()
                # Delete oldest entries by last_used_at
                cur.execute(
                    """
                    DELETE FROM translations WHERE id IN (
                        SELECT id FROM translations ORDER BY last_used_at ASC LIMIT ?
                    )
                    """,
                    (entries_to_remove,),
                )
                deleted = cur.rowcount
                conn.commit()
                logger.info("Cache cleanup: removed %d entries (was %d, limit %d)", deleted, count, CACHE_MAX_ENTRIES)
            finally:
                conn.close()

    def get_stats(self) -> Dict[str, int]:
        """Get cache statistics for monitoring."""
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM translations")
            total_entries = cur.fetchone()[0]

            # Get database file size
            db_size = 0
            if os.path.exists(self.db_path):
                db_size = os.path.getsize(self.db_path)

            return {
                "total_entries": total_entries,
                "db_size_bytes": db_size,
                "max_entries": CACHE_MAX_ENTRIES,
            }
        finally:
            conn.close()

    def close(self) -> None:
        """Close cache (no-op for connection-per-operation pattern)."""
        pass
