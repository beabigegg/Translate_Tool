"""Wikidata term lookup for multilingual terminology reference."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

_WIKIDATA_API = "https://www.wikidata.org/w/api.php"
_USER_AGENT = "TranslateTool/1.0 (local-translation-tool)"
_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": _USER_AGENT})

# Map our language names to Wikidata language codes
_LANG_TO_WIKIDATA: Dict[str, List[str]] = {
    "Chinese": ["zh", "zh-cn", "zh-tw", "zh-hans", "zh-hant"],
    "English": ["en"],
    "Vietnamese": ["vi"],
    "Japanese": ["ja"],
    "Korean": ["ko"],
    "French": ["fr"],
    "German": ["de"],
    "Spanish": ["es"],
    "Portuguese": ["pt"],
    "Russian": ["ru"],
    "Thai": ["th"],
    "Indonesian": ["id"],
    "Malay": ["ms"],
}

# Reverse: Wikidata code → our language name (first match wins)
_WIKIDATA_TO_LANG: Dict[str, str] = {}
for _name, _codes in _LANG_TO_WIKIDATA.items():
    for _code in _codes:
        _WIKIDATA_TO_LANG.setdefault(_code, _name)


def _wikidata_search_lang(lang_name: str) -> str:
    """Return the primary Wikidata language code for searching."""
    codes = _LANG_TO_WIKIDATA.get(lang_name)
    if codes:
        return codes[0]
    return lang_name.lower()[:2]


def _wikidata_label_langs(target_langs: List[str]) -> str:
    """Build the pipe-separated language list for wbgetentities."""
    codes: List[str] = []
    for lang in target_langs:
        codes.extend(_LANG_TO_WIKIDATA.get(lang, [lang.lower()[:2]]))
    # Always include en for fallback
    if "en" not in codes:
        codes.append("en")
    return "|".join(dict.fromkeys(codes))  # deduplicate, preserve order


def search_wikidata(
    term: str,
    source_lang: str = "Chinese",
    target_langs: Optional[List[str]] = None,
    limit: int = 3,
    timeout: float = 10.0,
) -> List[Dict]:
    """Search Wikidata for a term and return multilingual translations.

    Returns a list of candidate matches, each with:
      - entity_id: Wikidata entity ID (e.g. Q211387)
      - description: English description
      - labels: {lang_name: translation_text} for each target language found
    """
    if target_langs is None:
        target_langs = ["English"]

    search_lang = _wikidata_search_lang(source_lang)

    # Step 1: Search for matching entities
    try:
        resp = _SESSION.get(
            _WIKIDATA_API,
            params={
                "action": "wbsearchentities",
                "search": term,
                "language": search_lang,
                "format": "json",
                "limit": limit,
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        search_data = resp.json()
    except Exception as exc:
        logger.warning("[Wikidata] Search failed for %r: %s", term, exc)
        return []

    results = search_data.get("search", [])
    if not results:
        # Fallback: try English search
        if search_lang != "en":
            try:
                resp = _SESSION.get(
                    _WIKIDATA_API,
                    params={
                        "action": "wbsearchentities",
                        "search": term,
                        "language": "en",
                        "format": "json",
                        "limit": limit,
                    },
                    timeout=timeout,
                )
                resp.raise_for_status()
                search_data = resp.json()
                results = search_data.get("search", [])
            except Exception:
                pass
        if not results:
            return []

    # Step 2: Get multilingual labels for found entities
    entity_ids = [r["id"] for r in results]
    label_langs = _wikidata_label_langs([source_lang] + target_langs)

    try:
        resp = _SESSION.get(
            _WIKIDATA_API,
            params={
                "action": "wbgetentities",
                "ids": "|".join(entity_ids),
                "languages": label_langs,
                "props": "labels|descriptions|aliases",
                "format": "json",
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        entities_data = resp.json().get("entities", {})
    except Exception as exc:
        logger.warning("[Wikidata] Entity fetch failed: %s", exc)
        return []

    # Step 3: Build results
    candidates = []
    for entity_id in entity_ids:
        entity = entities_data.get(entity_id)
        if not entity:
            continue

        labels_raw = entity.get("labels", {})
        descriptions_raw = entity.get("descriptions", {})

        # Get description (prefer English)
        description = ""
        for desc_lang in ["en", search_lang]:
            if desc_lang in descriptions_raw:
                description = descriptions_raw[desc_lang]["value"]
                break

        # Get source label
        source_label = ""
        for code in _LANG_TO_WIKIDATA.get(source_lang, [search_lang]):
            if code in labels_raw:
                source_label = labels_raw[code]["value"]
                break

        # Get target labels
        target_labels: Dict[str, str] = {}
        for tgt_lang in target_langs:
            codes = _LANG_TO_WIKIDATA.get(tgt_lang, [tgt_lang.lower()[:2]])
            for code in codes:
                if code in labels_raw:
                    target_labels[tgt_lang] = labels_raw[code]["value"]
                    break

        candidates.append({
            "entity_id": entity_id,
            "source_label": source_label or term,
            "description": description,
            "labels": target_labels,
        })

    return candidates
