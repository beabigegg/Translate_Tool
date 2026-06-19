"""Terminology audit module (p2-term-audit).

Provides audit_terms() which measures whether approved glossary terms landed in
translated output and whether rejected terms leaked in. Designed to run over
the qe_blocks accumulator at the post_translate_hook seam in _run_job.

Design decisions:
  D-1: Default is case-insensitive exact substring match (zero NLP dependency).
  D-2: Runs over qe_blocks accumulator; NOT wired through translate_document().
  D-3: Result attached to JobRecord.audit (same lifecycle as JobQualityRecord).
  D-4: blingfire imported LAZILY inside the optional lemmatized branch only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from app.backend.services.term_db import TermDB


@dataclass
class TerminologyAuditResult:
    """Result of a per-job terminology audit.

    Exactly 5 fields per contracts/data/data-shape-contract.md §Terminology Audit.
    """
    terminology_hit_rate: float
    unapplied_terms: List[str]
    rejected_injections: List[str]
    total_approved: int
    matched_approved: int


def audit_terms(
    blocks: List[Tuple[str, str, str]],
    targets: List[str],
    domain: Optional[str],
    term_db: TermDB,
    lemmatized: bool = False,
) -> TerminologyAuditResult:
    """Audit translated blocks against the approved/rejected terminology sets.

    Args:
        blocks: List of (block_id, src, mt) tuples from the qe_blocks accumulator.
        targets: List of target language strings (scopes the term query).
        domain: Optional domain string (scopes the term query).
        term_db: TermDB instance for approved/rejected term queries.
        lemmatized: If True, use blingfire normalization before matching
            (optional mode, default off per D-1/D-4).

    Returns:
        TerminologyAuditResult with 5 fields.
    """
    # Collect all approved and rejected terms across targets
    approved_terms = []
    rejected_terms = []
    for target_lang in targets:
        approved_terms.extend(term_db.get_approved(target_lang, domain))
        rejected_terms.extend(term_db.get_rejected(target_lang, domain))

    total_approved = len(approved_terms)

    # Collect all mt text from blocks
    all_mt_text = " ".join(mt for _, _, mt in blocks)

    # Optional lemmatized normalization (D-4: lazy import)
    if lemmatized:
        try:
            import blingfire  # type: ignore[import]  # noqa: F401
            # Apply lightweight normalization to mt text
            all_mt_normalized = blingfire.text_to_words(all_mt_text).lower()
        except Exception:
            # If blingfire unavailable, fall back to lowercase
            all_mt_normalized = all_mt_text.lower()
    else:
        all_mt_normalized = all_mt_text.lower()

    # --- Approved term matching (D-1: case-insensitive exact substring) ---
    matched_approved = 0
    unapplied_terms: List[str] = []

    for term in approved_terms:
        target_text_lower = term.target_text.lower()
        if target_text_lower in all_mt_normalized:
            matched_approved += 1
        else:
            unapplied_terms.append(term.source_text)

    # Compute hit rate — vacuous 1.0 when no approved terms (BR-60)
    if total_approved == 0:
        terminology_hit_rate = 1.0
    else:
        terminology_hit_rate = matched_approved / total_approved

    # --- Rejected term detection (whole-token boundary check per design.md §Open Risks) ---
    rejected_injections: List[str] = []

    for term in rejected_terms:
        target_text = term.target_text
        # Use word-boundary regex to avoid flagging substrings of longer tokens
        # re.escape handles special regex characters in the term text
        pattern = re.compile(
            r"\b" + re.escape(target_text) + r"\b",
            re.IGNORECASE,
        )
        if pattern.search(all_mt_text):
            rejected_injections.append(target_text)

    return TerminologyAuditResult(
        terminology_hit_rate=terminology_hit_rate,
        unapplied_terms=unapplied_terms,
        rejected_injections=rejected_injections,
        total_approved=total_approved,
        matched_approved=matched_approved,
    )
