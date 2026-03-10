"""Term database backed by SQLite."""

from __future__ import annotations

import csv
import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from app.backend.models.term import Term

logger = logging.getLogger(__name__)

_DB_LOCK = threading.Lock()

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS terms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_text TEXT NOT NULL,
    target_text TEXT NOT NULL,
    source_lang TEXT NOT NULL,
    target_lang TEXT NOT NULL,
    domain TEXT NOT NULL DEFAULT 'general',
    context_snippet TEXT NOT NULL DEFAULT '',
    confidence REAL NOT NULL DEFAULT 1.0,
    usage_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'unverified',
    created_at TEXT NOT NULL,
    UNIQUE (source_text, target_lang, domain)
);
"""

_MIGRATE_ADD_STATUS_SQL = """
ALTER TABLE terms ADD COLUMN status TEXT NOT NULL DEFAULT 'unverified';
"""


class TermDB:
    """Persistent term database stored in a local SQLite file."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        if db_path is None:
            from app.backend.config import DATA_DIR
            db_path = DATA_DIR / "term_db.sqlite"

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with _DB_LOCK, self._connect() as conn:
            conn.execute(_CREATE_TABLE_SQL)
            conn.commit()
            # Migration: add status column if absent (existing DBs)
            cols = {r[1] for r in conn.execute("PRAGMA table_info(terms)").fetchall()}
            if "status" not in cols:
                conn.execute(_MIGRATE_ADD_STATUS_SQL)
                conn.commit()
                logger.info("[TermDB] Migrated: added status column")

    # ------------------------------------------------------------------
    # Query methods
    # ------------------------------------------------------------------

    def exists(self, source_text: str, target_lang: str, domain: str) -> bool:
        """Return True if (source_text, target_lang, domain) is already stored."""
        with _DB_LOCK, self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM terms WHERE source_text=? AND target_lang=? AND domain=?",
                (source_text, target_lang, domain),
            ).fetchone()
        return row is not None

    def get_unknown(
        self, candidates: List[Dict], target_lang: str, domain: str
    ) -> List[Dict]:
        """Return candidates whose (term, target_lang, domain) are NOT in the DB."""
        unknown = []
        for c in candidates:
            term = c.get("term") or c.get("source_text", "")
            if not term:
                continue
            if not self.exists(term, target_lang, domain):
                unknown.append(c)
        return unknown

    def get_top_terms(
        self, target_lang: str, domain: str, top_n: int = 30
    ) -> List[Term]:
        """Return top N injection-safe terms (approved or confidence=1.0)."""
        with _DB_LOCK, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM terms
                WHERE target_lang=? AND domain=?
                  AND (status='approved' OR confidence=1.0)
                ORDER BY usage_count DESC
                LIMIT ?
                """,
                (target_lang, domain, top_n),
            ).fetchall()
        return [_row_to_term(r) for r in rows]

    def get_document_terms(
        self,
        target_lang: str,
        domain: str,
        source_texts: List[str],
    ) -> List[Term]:
        """Return injection-safe terms matching the given source_texts.

        Only returns terms with status='approved' OR confidence=1.0,
        scoped to the current document's extracted terms.
        """
        if not source_texts:
            return []
        with _DB_LOCK, self._connect() as conn:
            placeholders = ",".join("?" for _ in source_texts)
            rows = conn.execute(
                f"""
                SELECT * FROM terms
                WHERE target_lang=? AND domain=?
                  AND (status='approved' OR confidence=1.0)
                  AND source_text IN ({placeholders})
                ORDER BY confidence DESC, usage_count DESC
                """,
                [target_lang, domain] + list(source_texts),
            ).fetchall()
        return [_row_to_term(r) for r in rows]

    # ------------------------------------------------------------------
    # Write methods
    # ------------------------------------------------------------------

    def insert(self, term: Term, strategy: str = "skip") -> str:
        """Insert a term with the given conflict strategy.

        Strategies:
          skip      – never overwrite (safe default)
          overwrite – update unverified records; PROTECTS approved records
          merge     – overwrite only if imported confidence > existing; PROTECTS approved
          force     – overwrites everything, including approved (intentional correction)

        Returns: 'inserted', 'skipped', or 'overwritten'.
        """
        with _DB_LOCK, self._connect() as conn:
            existing = conn.execute(
                "SELECT id, confidence, status FROM terms WHERE source_text=? AND target_lang=? AND domain=?",
                (term.source_text, term.target_lang, term.domain),
            ).fetchone()

            if existing is None:
                conn.execute(
                    """
                    INSERT INTO terms
                        (source_text, target_text, source_lang, target_lang,
                         domain, context_snippet, confidence, usage_count, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        term.source_text,
                        term.target_text,
                        term.source_lang,
                        term.target_lang,
                        term.domain,
                        term.context_snippet,
                        term.confidence,
                        term.usage_count,
                        term.status,
                        term.created_at or _now_iso(),
                    ),
                )
                conn.commit()
                return "inserted"

            existing_approved = existing["status"] == "approved"

            # Conflict resolution
            if strategy == "skip":
                return "skipped"

            if strategy == "overwrite":
                # Protect approved records — use 'force' for intentional correction
                if existing_approved:
                    return "skipped"
                conn.execute(
                    """
                    UPDATE terms SET
                        target_text=?, source_lang=?, context_snippet=?,
                        confidence=?, usage_count=?, status=?, created_at=?
                    WHERE source_text=? AND target_lang=? AND domain=?
                    """,
                    (
                        term.target_text, term.source_lang, term.context_snippet,
                        term.confidence, term.usage_count, term.status,
                        term.created_at or _now_iso(),
                        term.source_text, term.target_lang, term.domain,
                    ),
                )
                conn.commit()
                return "overwritten"

            if strategy == "force":
                # Intentional correction — overwrites approved records too
                conn.execute(
                    """
                    UPDATE terms SET
                        target_text=?, source_lang=?, context_snippet=?,
                        confidence=?, usage_count=?, status=?, created_at=?
                    WHERE source_text=? AND target_lang=? AND domain=?
                    """,
                    (
                        term.target_text, term.source_lang, term.context_snippet,
                        term.confidence, term.usage_count, term.status,
                        term.created_at or _now_iso(),
                        term.source_text, term.target_lang, term.domain,
                    ),
                )
                conn.commit()
                return "overwritten"

            if strategy == "merge":
                # Protect approved; for unverified: take higher confidence
                if existing_approved:
                    return "skipped"
                existing_confidence = existing["confidence"]
                if term.confidence > existing_confidence:
                    conn.execute(
                        """
                        UPDATE terms SET
                            target_text=?, source_lang=?, context_snippet=?,
                            confidence=?, status=?, created_at=?
                        WHERE source_text=? AND target_lang=? AND domain=?
                        """,
                        (
                            term.target_text, term.source_lang, term.context_snippet,
                            term.confidence, term.status,
                            term.created_at or _now_iso(),
                            term.source_text, term.target_lang, term.domain,
                        ),
                    )
                    conn.commit()
                    return "overwritten"
                return "skipped"

        return "skipped"

    def edit_term(
        self,
        source_text: str,
        target_lang: str,
        domain: str,
        *,
        target_text: str,
        confidence: Optional[float] = None,
    ) -> bool:
        """Update target_text (and optionally confidence) of any term, keeping status='approved'.

        Returns True if the term was found and updated.
        """
        with _DB_LOCK, self._connect() as conn:
            if confidence is not None:
                cur = conn.execute(
                    """
                    UPDATE terms SET target_text=?, confidence=?, status='approved'
                    WHERE source_text=? AND target_lang=? AND domain=?
                    """,
                    (target_text, confidence, source_text, target_lang, domain),
                )
            else:
                cur = conn.execute(
                    """
                    UPDATE terms SET target_text=?, status='approved'
                    WHERE source_text=? AND target_lang=? AND domain=?
                    """,
                    (target_text, source_text, target_lang, domain),
                )
            conn.commit()
        return cur.rowcount > 0

    def approve(self, source_text: str, target_lang: str, domain: str) -> bool:
        """Set status='approved' for a term. Returns True if the term was found."""
        with _DB_LOCK, self._connect() as conn:
            cur = conn.execute(
                "UPDATE terms SET status='approved' WHERE source_text=? AND target_lang=? AND domain=?",
                (source_text, target_lang, domain),
            )
            conn.commit()
        return cur.rowcount > 0

    def get_unverified(
        self,
        target_lang: Optional[str] = None,
        domain: Optional[str] = None,
    ) -> List[Term]:
        """Return all unverified terms, optionally filtered."""
        conditions = ["status='unverified'"]
        params: list = []
        if target_lang:
            conditions.append("target_lang=?")
            params.append(target_lang)
        if domain:
            conditions.append("domain=?")
            params.append(domain)
        sql = f"SELECT * FROM terms WHERE {' AND '.join(conditions)} ORDER BY id DESC"
        with _DB_LOCK, self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_row_to_term(r) for r in rows]

    def increment_usage(self, source_text: str, target_lang: str, domain: str) -> None:
        """Increment usage_count for a term."""
        with _DB_LOCK, self._connect() as conn:
            conn.execute(
                """
                UPDATE terms SET usage_count = usage_count + 1
                WHERE source_text=? AND target_lang=? AND domain=?
                """,
                (source_text, target_lang, domain),
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict:
        """Return total / unverified / by_target_lang / by_domain statistics."""
        with _DB_LOCK, self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM terms").fetchone()[0]
            unverified = conn.execute(
                "SELECT COUNT(*) FROM terms WHERE status='unverified'"
            ).fetchone()[0]
            by_lang_rows = conn.execute(
                "SELECT target_lang, COUNT(*) as cnt FROM terms GROUP BY target_lang"
            ).fetchall()
            by_domain_rows = conn.execute(
                "SELECT domain, COUNT(*) as cnt FROM terms GROUP BY domain"
            ).fetchall()
        return {
            "total": total,
            "unverified": unverified,
            "by_target_lang": {r["target_lang"]: r["cnt"] for r in by_lang_rows},
            "by_domain": {r["domain"]: r["cnt"] for r in by_domain_rows},
        }

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def get_approved(
        self,
        target_lang: Optional[str] = None,
        domain: Optional[str] = None,
    ) -> List[Term]:
        """Return all approved terms, optionally filtered."""
        conditions = ["status='approved'"]
        params: list = []
        if target_lang:
            conditions.append("target_lang=?")
            params.append(target_lang)
        if domain:
            conditions.append("domain=?")
            params.append(domain)
        sql = f"SELECT * FROM terms WHERE {' AND '.join(conditions)} ORDER BY id DESC"
        with _DB_LOCK, self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_row_to_term(r) for r in rows]

    def export_json(self, path: Path, status_filter: Optional[str] = None) -> None:
        """Export terms to a JSON file. status_filter: 'approved' | 'unverified' | None (all)."""
        terms = self._all_terms(status_filter)
        payload = {
            "version": 1,
            "exported_at": _now_iso(),
            "terms": [_term_to_dict(t) for t in terms],
        }
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def export_csv(self, path: Path, status_filter: Optional[str] = None) -> None:
        """Export terms to a CSV file. status_filter: 'approved' | 'unverified' | None (all)."""
        terms = self._all_terms(status_filter)
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = [
            "source_text", "target_text", "source_lang", "target_lang",
            "domain", "context_snippet", "confidence", "usage_count", "status",
        ]
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for t in terms:
                writer.writerow({k: getattr(t, k) for k in fieldnames})

    def export_xlsx(self, path: Path, status_filter: Optional[str] = None) -> None:
        """Export terms to an XLSX file. status_filter: 'approved' | 'unverified' | None (all)."""
        try:
            import openpyxl
        except ImportError:
            raise RuntimeError("openpyxl is required for XLSX export. Install it with: pip install openpyxl")

        terms = self._all_terms(status_filter)
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Group by target_lang
        by_lang: Dict[str, List[Term]] = {}
        for t in terms:
            by_lang.setdefault(t.target_lang, []).append(t)

        wb = openpyxl.Workbook()
        wb.remove(wb.active)  # Remove default sheet

        headers = [
            "source_text", "target_text", "source_lang", "target_lang",
            "domain", "context_snippet", "confidence", "usage_count", "status",
        ]
        for lang, lang_terms in by_lang.items():
            ws = wb.create_sheet(title=lang[:31])  # Sheet names max 31 chars
            ws.append(headers)
            for t in lang_terms:
                ws.append([getattr(t, h) for h in headers])

        if not wb.worksheets:
            wb.create_sheet("terms")

        wb.save(str(path))

    # ------------------------------------------------------------------
    # Import
    # ------------------------------------------------------------------

    def import_file(self, path: Path, strategy: str = "skip") -> Dict[str, int]:
        """Import terms from a JSON or CSV file.

        Returns counts: inserted / skipped / overwritten.
        """
        path = Path(path)
        suffix = path.suffix.lower()

        if suffix == ".json":
            terms = self._parse_json_import(path)
        elif suffix == ".csv":
            terms = self._parse_csv_import(path)
        else:
            raise ValueError(f"Unsupported import format: {suffix}")

        counts: Dict[str, int] = {"inserted": 0, "skipped": 0, "overwritten": 0}
        for term in terms:
            result = self.insert(term, strategy=strategy)
            counts[result] = counts.get(result, 0) + 1

        logger.info(
            "[TermDB] Import complete: inserted=%d skipped=%d overwritten=%d",
            counts["inserted"], counts["skipped"], counts["overwritten"],
        )
        return counts

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _all_terms(self, status_filter: Optional[str] = None) -> List[Term]:
        sql = "SELECT * FROM terms"
        params: list = []
        if status_filter in ("approved", "unverified"):
            sql += " WHERE status=?"
            params.append(status_filter)
        sql += " ORDER BY id"
        with _DB_LOCK, self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_row_to_term(r) for r in rows]

    def _parse_json_import(self, path: Path) -> List[Term]:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        raw_terms = data.get("terms", data) if isinstance(data, dict) else data
        return [_dict_to_term(d) for d in raw_terms if isinstance(d, dict)]

    def _parse_csv_import(self, path: Path) -> List[Term]:
        terms: List[Term] = []
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                terms.append(_dict_to_term(dict(row)))
        return terms


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_term(row: sqlite3.Row) -> Term:
    return Term(
        source_text=row["source_text"],
        target_text=row["target_text"],
        source_lang=row["source_lang"],
        target_lang=row["target_lang"],
        domain=row["domain"],
        context_snippet=row["context_snippet"],
        confidence=float(row["confidence"]),
        usage_count=int(row["usage_count"]),
        status=row["status"] if "status" in row.keys() else "unverified",
        created_at=row["created_at"],
    )


def _term_to_dict(t: Term) -> Dict:
    return {
        "source_text": t.source_text,
        "target_text": t.target_text,
        "source_lang": t.source_lang,
        "target_lang": t.target_lang,
        "domain": t.domain,
        "context_snippet": t.context_snippet,
        "confidence": t.confidence,
        "usage_count": t.usage_count,
        "status": t.status,
    }


def _dict_to_term(d: Dict) -> Term:
    """Convert an import dict to a Term. Defaults status to 'approved' (human-curated import)."""
    return Term(
        source_text=str(d.get("source_text", "")),
        target_text=str(d.get("target_text", "")),
        source_lang=str(d.get("source_lang", "")),
        target_lang=str(d.get("target_lang", "")),
        domain=str(d.get("domain", "general")),
        context_snippet=str(d.get("context_snippet", "")),
        confidence=float(d.get("confidence", 1.0)),
        usage_count=int(d.get("usage_count", 0)),
        status=str(d.get("status", "approved")),  # imports are human-curated
        created_at=str(d.get("created_at") or _now_iso()),
    )
