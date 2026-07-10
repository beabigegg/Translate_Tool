"""Shared JSON-translation instruction phrasing and body envelope (BR-111, BR-112).

Single source of truth for the probe-validated instruction phrasing used by the
`translate_json` client seam (json-structured-translation-io). Both the table
wire format (`table_serializer.serialize_json`/`parse_json`) and the body
envelope defined here share the same pinned phrasing rules:

- MUST contain the `Return: {"translation": <your translation>}` framing (or,
  for the table payload, its per-cell analogue) — this is the ONLY phrasing
  validated live against PANJIT/gpt-oss:120b, deepseek-chat, and the long_doc
  MLX model (see design.md Finding 2/3).
- MUST NOT contain `Reply ONLY with JSON` or `Output a JSON object with a
  single key` — both make the gpt-oss:120b reasoning model return an empty
  `content` with `finish_reason: stop`.
- MUST NOT be re-wrapped by `translate_once`'s "Translate the following
  text... Output only the translation" framing — the caller passes the string
  built here directly to `client.translate_json(...)`, never to
  `translate_once(...)`.

This module MUST NOT import a logger or emit any log line itself (IP-9): the
caller (the table site or `translate_merged_paragraphs`) owns the single INFO
fallback line via the job `log(...)` callback.
"""

from __future__ import annotations

import json
from typing import Any, Optional, Tuple

# ---------------------------------------------------------------------------
# Pinned instruction templates (BR-111) — do not mirror this phrasing anywhere
# else; both clients' `translate_json` receive the fully-built string from the
# functions below and pass it through unmodified.
# ---------------------------------------------------------------------------

_BODY_INSTRUCTION_TEMPLATE = (
    'Translate the "text" value in the JSON object below from {src} to {tgt}. '
    'Return: {{"translation": <your translation>}}\n\n'
    "{payload_json}"
)

_TABLE_INSTRUCTION_TEMPLATE = (
    "Translate the \"text\" value of each cell below from {src} to {tgt}. "
    "Each cell is identified by its row and col; use the exact same row/col "
    "values in your reply. "
    'Return: {{"cells": [{{"row": <int>, "col": <int>, '
    '"translation": <your translation>}}, ...]}}\n\n'
    "{cells_json}"
)


def build_body_payload(text: str, src_lang: Optional[str], tgt_lang: str) -> str:
    """Build the JSON-envelope user payload for a body/paragraph segment (BR-112).

    Sends ``{"text": text}`` framed by the pinned instruction, BEFORE the
    envelope (BR-80 ordering invariant). This string is passed directly to
    `client.translate_json(...)` — never to `translate_once(...)`.

    Args:
        text: The segment to translate (already past the BR-107 guard).
        src_lang: Source language code/name, or None/"auto".
        tgt_lang: Target language code/name.

    Returns:
        The full user payload string ready for `translate_json`.
    """
    src = src_lang or "auto"
    payload_json = json.dumps({"text": text}, ensure_ascii=False)
    return _BODY_INSTRUCTION_TEMPLATE.format(src=src, tgt=tgt_lang, payload_json=payload_json)


def build_table_payload(cells: Any, src_lang: Optional[str], tgt_lang: str) -> str:
    """Build the JSON-envelope user payload for a whole-table call (BR-79/BR-80).

    Serializes `cells` via `table_serializer.serialize_json` (content-bearing,
    non-numeric cells only, original `(row, col)` coordinates) and frames it
    with the pinned per-cell instruction, BEFORE the serialized cell list.

    Args:
        cells: Iterable of cell objects (row/col/content/is_numeric attrs).
        src_lang: Source language code/name, or None/"auto".
        tgt_lang: Target language code/name.

    Returns:
        The full user payload string ready for `translate_json`.
    """
    from app.backend.utils import table_serializer

    src = src_lang or "auto"
    cells_json = table_serializer.serialize_json(cells)
    return _TABLE_INSTRUCTION_TEMPLATE.format(src=src, tgt=tgt_lang, cells_json=cells_json)


def parse_body_reply(content: str, source_text: str) -> Tuple[Optional[str], str]:
    """Parse and validate a body-path JSON reply (BR-112).

    Args:
        content: The raw reply string from `client.translate_json`.
        source_text: The original segment sent, for the echoed-source check.

    Returns:
        ``(translation, "")`` on a valid, non-echoed reply; ``(None, reason)``
        on any of: empty content, unparseable JSON, a reply that isn't a JSON
        object, a missing or non-string ``translation`` key, or
        ``translation == source_text`` (an echoed, untranslated reply).
    """
    if not content:
        return None, "empty content"
    try:
        data = json.loads(content)
    except (ValueError, TypeError):
        return None, "unparseable JSON"
    if not isinstance(data, dict):
        return None, "reply is not a JSON object"
    translation = data.get("translation")
    if not isinstance(translation, str):
        return None, "missing or non-string 'translation' key"
    if translation == source_text:
        return None, "echoed source (untranslated reply)"
    return translation, ""
