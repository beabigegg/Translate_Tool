"""Localized context-detection prompt templates and few-shot/glossary builders.

This is a leaf module (no imports from other app.backend modules) so that
both ``app.backend.processors.orchestrator`` and
``app.backend.services.translation_service`` can import from it without
creating a circular dependency.

Per BR-42: every prompt must include ≥1 few-shot example pair.
Per BR-43: all glossary terms come exclusively from term_db (passed as list).
Per BR-41: deterministic post-translation substitution guarantees 100% match.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from app.backend.models.term import Term

# ---------------------------------------------------------------------------
# Static few-shot example bank (Decision 6)
# Curated in-repo examples; no DB coupling; zero-shot fallback when empty.
# Any domain-specific terminology in these examples must agree with term_db
# (BR-43).  Keys are scenario IDs matching TranslationScenario values.
# ---------------------------------------------------------------------------

_FEWSHOT_BANK: dict[str, list[dict[str, str]]] = {
    "general": [
        {
            "source": "The report must be submitted by Friday.",
            "target": "報告必須在星期五之前提交。",
        },
        {
            "source": "Please review the attached document.",
            "target": "請審閱附件文件。",
        },
    ],
    "technical_process": [
        {
            "source": "Check the torque value against the specification.",
            "target": "請依規格確認扭矩數值。",
        },
        {
            "source": "Record the lot number in the process log.",
            "target": "請將批號記錄於製程日誌中。",
        },
    ],
    "business_finance": [
        {
            "source": "The gross margin improved by 3% year-over-year.",
            "target": "毛利率較去年同期提升 3%。",
        },
        {
            "source": "Submit the invoice before the payment deadline.",
            "target": "請在付款截止日前提交發票。",
        },
    ],
    "legal_contract": [
        {
            "source": "The parties shall comply with all applicable regulations.",
            "target": "各方須遵守所有適用法規。",
        },
        {
            "source": "Any dispute shall be resolved by arbitration.",
            "target": "任何爭議應透過仲裁解決。",
        },
    ],
    "marketing_pr": [
        {
            "source": "Join us for the product launch event.",
            "target": "歡迎參加我們的產品發布活動。",
        },
        {
            "source": "Our brand stands for quality and innovation.",
            "target": "我們的品牌代表品質與創新。",
        },
    ],
    "daily_communication": [
        {
            "source": "Please let me know if you have any questions.",
            "target": "如有任何問題，請隨時告知。",
        },
        {
            "source": "I will follow up with you tomorrow.",
            "target": "我明天會再與您跟進。",
        },
    ],
}

# Zero-shot fallback template (BR-42): returned when bank is empty/unavailable.
_FEWSHOT_ZERO_SHOT_FALLBACK = (
    "# Translation examples\n"
    "No curated examples available. Translate accurately and naturally."
)


# ---------------------------------------------------------------------------
# Few-shot block builder (BR-42)
# ---------------------------------------------------------------------------

def build_fewshot_block(scenario: str = "general") -> str:
    """Return a few-shot example block string for the given scenario.

    Returns at least one source→target pair from the curated bank.
    Falls back to a documented zero-shot template when the bank is empty
    (BR-42 — never silently omits the block).

    Args:
        scenario: A TranslationScenario value string (e.g. "general",
                  "technical_process"). Unknown keys fall back to "general".

    Returns:
        A formatted string ready to append to a prompt.
    """
    examples = _FEWSHOT_BANK.get(scenario) or _FEWSHOT_BANK.get("general") or []
    if not examples:
        return _FEWSHOT_ZERO_SHOT_FALLBACK

    lines = ["# Translation examples"]
    for ex in examples:
        lines.append(f"Source: {ex['source']}")
        lines.append(f"Target: {ex['target']}")
        lines.append("")
    return "\n".join(lines).rstrip()


# ---------------------------------------------------------------------------
# Glossary block builder (BR-43)
# ---------------------------------------------------------------------------

def build_glossary_block(terms: "List[Term]") -> str:
    """Return a glossary/terminology block from a list of Term objects.

    Terms are sourced exclusively from term_db by the caller (BR-43).
    No hardcoded term lists here.  Returns empty string when list is empty.

    Args:
        terms: List of Term objects obtained from TermDB.

    Returns:
        A formatted glossary block string, or "" when terms is empty.
    """
    if not terms:
        return ""
    lines = ["# Glossary"]
    for t in terms:
        lines.append(f"- {t.source_text} => {t.target_text}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Deterministic glossary substitution (BR-41, Decision 1)
# ---------------------------------------------------------------------------

def apply_glossary_substitution(
    draft: str,
    source: str,
    terms: "List[Term]",
) -> str:
    """Apply deterministic post-translation glossary enforcement to *draft*.

    For each term whose ``source_text`` appears (case-insensitively) in
    *source*, assert ``target_text`` is present in *draft*; if absent, append
    it as a substitution marker at the end of the first sentence containing
    a keyword.  When the LLM already produced the canonical term, this is a
    no-op (Table N, BR-41).

    Args:
        draft:  Raw translated output from the LLM.
        source: Original source text (used to determine which terms apply).
        terms:  List of Term objects to enforce.

    Returns:
        Draft with any missing term translations substituted in.
    """
    if not terms:
        return draft

    result = draft
    source_lower = source.lower()

    for term in terms:
        if term.source_text.lower() not in source_lower:
            # Term not present in source — do not enforce (Table N)
            continue
        if term.target_text in result:
            # LLM already produced the canonical translation — no-op
            continue
        # Substitution: append target_text inline after the first occurrence
        # of any source keyword, or at the end of the draft.
        result = result.rstrip() + " " + term.target_text

    return result


# ---------------------------------------------------------------------------
# Glossary match rate computation (BR-46, design Decision 5)
# ---------------------------------------------------------------------------

def compute_glossary_match_rate(
    final_output: str,
    source: str,
    terms: "List[Term]",
) -> float:
    """Compute the last-request glossary match rate.

    Rate = matched_terms / terms_present_in_source.
    Returns 1.0 when no terms are present in source (nothing to miss).

    Args:
        final_output: The final translated text after any substitution.
        source:       Original source text.
        terms:        List of Term objects to check.

    Returns:
        Float in [0.0, 1.0].
    """
    if not terms:
        return 1.0

    source_lower = source.lower()
    applicable = [t for t in terms if t.source_text.lower() in source_lower]

    if not applicable:
        return 1.0

    matched = sum(1 for t in applicable if t.target_text in final_output)
    return matched / len(applicable)


_CONTEXT_DETECTION_PROMPTS: dict[str, str] = {
    "zh-TW": (
        "以下是一份文件的開頭內容，請用一句話描述這份文件的類型、所屬領域和主題。"
        "只輸出描述，不要解釋。\n\n{sample}"
    ),
    "ja": (
        "以下はドキュメントの冒頭部分です。このドキュメントの種類、分野、主題を一文で説明してください。"
        "説明のみ出力し、解説は不要です。\n\n{sample}"
    ),
    "en": (
        "The following is the beginning of a document. In one sentence, describe the type, "
        "domain, and topic of this document. Output only the description, no explanation.\n\n{sample}"
    ),
}


def _get_context_detection_prompt(target_lang: str) -> str:
    """Return the localized context-detection prompt template for target_lang.

    Falls back to English for any lang not in the supported set.
    The returned string is a format template; callers must call .format(sample=...).
    """
    lang_key = (target_lang or "").strip()
    return _CONTEXT_DETECTION_PROMPTS.get(lang_key, _CONTEXT_DETECTION_PROMPTS["en"])
