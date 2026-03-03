"""Persistent SQLite translation cache.

Caches translation results keyed by sha256(source_text, target_lang, src_lang, model).
Cache hits bypass Ollama entirely, dramatically speeding up repeated translations.
"""

from __future__ import annotations

import hashlib
import logging
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.backend.config import CACHE_DIR, TRANSLATION_CACHE_ENABLED

logger = logging.getLogger(__name__)

_SCHEMA_VERSION = 1
_VAR_CHUNK_SIZE = 900  # SQLite variable limit safety margin


def _make_key(text: str, target_lang: str, src_lang: str, model: str) -> str:
    """Compute cache key as sha256 hex digest."""
    payload = "\x00".join([
        text.strip(),
        target_lang.lower(),
        src_lang.lower(),
        model.lower(),
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class TranslationCache:
    """Thread-safe SQLite translation cache with WAL mode."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._db_path = db_path or (CACHE_DIR / "translations.db")
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_lock = threading.Lock()
        # Eagerly create schema on the calling thread
        self._get_conn()
        logger.info("Translation cache initialized: %s", self._db_path)

    def _get_conn(self) -> sqlite3.Connection:
        """Return a thread-local SQLite connection, creating if needed."""
        conn: Optional[sqlite3.Connection] = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(str(self._db_path), timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            self._local.conn = conn
            self._ensure_schema(conn)
        return conn

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        """Create tables if they don't exist."""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS translations (
                key_hash    TEXT PRIMARY KEY,
                source_text TEXT NOT NULL,
                target_lang TEXT NOT NULL,
                src_lang    TEXT NOT NULL,
                model       TEXT NOT NULL,
                translation TEXT NOT NULL,
                created_at  REAL NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cache_meta (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        # Store schema version
        conn.execute(
            "INSERT OR IGNORE INTO cache_meta (key, value) VALUES (?, ?)",
            ("schema_version", str(_SCHEMA_VERSION)),
        )
        conn.commit()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_batch(
        self,
        texts: List[str],
        target_lang: str,
        src_lang: str,
        model: str,
    ) -> Dict[str, str]:
        """Look up cached translations for a batch of source texts.

        Returns:
            Dict mapping source_text -> cached translation (only hits).
        """
        if not texts:
            return {}

        key_to_text: Dict[str, str] = {}
        for t in texts:
            k = _make_key(t, target_lang, src_lang, model)
            key_to_text[k] = t

        conn = self._get_conn()
        result: Dict[str, str] = {}
        keys = list(key_to_text.keys())

        # Query in chunks to stay within SQLite variable limit
        for i in range(0, len(keys), _VAR_CHUNK_SIZE):
            chunk = keys[i : i + _VAR_CHUNK_SIZE]
            placeholders = ",".join("?" * len(chunk))
            rows = conn.execute(
                f"SELECT key_hash, translation FROM translations WHERE key_hash IN ({placeholders})",
                chunk,
            ).fetchall()
            for key_hash, translation in rows:
                src_text = key_to_text[key_hash]
                result[src_text] = translation

        return result

    def put_batch(
        self,
        entries: List[Tuple[str, str, str, str, str]],
    ) -> None:
        """Store multiple translation results.

        Args:
            entries: List of (source_text, target_lang, src_lang, model, translation).
        """
        if not entries:
            return

        conn = self._get_conn()
        now = time.time()
        rows = []
        for source_text, target_lang, src_lang, model, translation in entries:
            key_hash = _make_key(source_text, target_lang, src_lang, model)
            rows.append((
                key_hash, source_text, target_lang, src_lang, model, translation, now,
            ))

        conn.executemany(
            """INSERT OR IGNORE INTO translations
               (key_hash, source_text, target_lang, src_lang, model, translation, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        conn.commit()

    def put(
        self,
        source_text: str,
        target_lang: str,
        src_lang: str,
        model: str,
        translation: str,
    ) -> None:
        """Store a single translation result."""
        self.put_batch([(source_text, target_lang, src_lang, model, translation)])

    def clear(self, model: Optional[str] = None) -> int:
        """Clear cache entries. If model is given, only clear that model's entries.

        Returns:
            Number of entries deleted.
        """
        conn = self._get_conn()
        if model:
            cursor = conn.execute(
                "DELETE FROM translations WHERE LOWER(model) = ? OR LOWER(model) LIKE ?",
                (model.lower(), f"{model.lower()}::%"),
            )
        else:
            cursor = conn.execute("DELETE FROM translations")
        conn.commit()
        deleted = cursor.rowcount
        if deleted > 0:
            conn.execute("VACUUM")
        logger.info("Cache cleared: %d entries deleted (model=%s)", deleted, model or "all")
        return deleted

    def stats(self) -> Dict:
        """Return cache statistics."""
        conn = self._get_conn()
        row = conn.execute("SELECT COUNT(*) FROM translations").fetchone()
        entries = row[0] if row else 0

        db_size = 0
        try:
            db_size = os.path.getsize(self._db_path)
        except OSError:
            pass

        return {
            "entries": entries,
            "db_size_bytes": db_size,
            "db_path": str(self._db_path),
        }


# ------------------------------------------------------------------
# Module-level singleton
# ------------------------------------------------------------------

_cache_instance: Optional[TranslationCache] = None
_cache_lock = threading.Lock()


def get_cache() -> Optional[TranslationCache]:
    """Return the global TranslationCache singleton, or None if disabled."""
    global _cache_instance

    if not TRANSLATION_CACHE_ENABLED:
        return None

    if _cache_instance is not None:
        return _cache_instance

    with _cache_lock:
        # Double-check after acquiring lock
        if _cache_instance is None:
            _cache_instance = TranslationCache()
        return _cache_instance
