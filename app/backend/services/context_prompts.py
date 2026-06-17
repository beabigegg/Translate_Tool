"""Localized context-detection prompt templates.

This is a leaf module (no imports from other app.backend modules) so that
both ``app.backend.processors.orchestrator`` and
``app.backend.services.translation_service`` can import from it without
creating a circular dependency.
"""

from __future__ import annotations

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
