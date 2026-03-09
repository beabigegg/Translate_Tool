"""Phase 0 terminology extraction and translation using local Qwen 9B."""

from __future__ import annotations

import json
import logging
import re
from typing import Callable, Dict, List, Optional

try:
    from json_repair import repair_json as _repair_json
    _HAS_JSON_REPAIR = True
except ImportError:  # pragma: no cover
    _HAS_JSON_REPAIR = False

from app.backend.config import DEFAULT_MODEL, OLLAMA_BASE_URL, TimeoutConfig
from app.backend.models.term import Term
from app.backend.services.term_db import TermDB

logger = logging.getLogger(__name__)

# Scenario → domain mapping (Decision 3 from design.md)
SCENARIO_TO_DOMAIN: Dict[str, str] = {
    "TECHNICAL_PROCESS": "technical",
    "technical_process": "technical",
    "BUSINESS_FINANCE": "finance",
    "business_finance": "finance",
    "LEGAL_CONTRACT": "legal",
    "legal_contract": "legal",
    "MARKETING_PR": "marketing",
    "marketing_pr": "marketing",
    "DAILY_COMMUNICATION": "general",
    "daily_communication": "general",
    "GENERAL": "general",
    "general": "general",
    # Legacy aliases
    "SEMICONDUCTOR_OI_CP_SOP": "technical",
    "semiconductor_oi_cp_sop": "technical",
    "PROCESS_PRESENTATION": "technical",
    "process_presentation": "technical",
    "INTERNATIONAL_STANDARD": "legal",
    "international_standard": "legal",
    "BUSINESS_EMAIL": "finance",
    "business_email": "finance",
}

_EXTRACTION_PROMPT_TEMPLATE = """\
你是術語提取專家。請從以下【{domain}】領域文本中，提取所有專有名詞。
包含：品牌名稱、型號、設備名稱、縮寫、製程術語、動作術語、品質術語。
排除：
- 一般動詞、形容詞、介詞
- 數字、單位、數值範圍（如 100mm、±0.5）
- 文件編號、表單編號、版本號（如 SOP-001、Rev.1、Form-A）
- 料號、品號（如 P/N: xxxxx）
- 純代碼縮寫（如 OK、N/A、TBD）

輸出格式為 JSON array，不要任何額外說明：
[{{"term": "...", "context": "...（術語出現的短語，10字以內）"}}, ...]

文本：
{segment_text}"""

_TRANSLATION_PROMPT_TEMPLATE = """\
你是專業術語翻譯員。將以下【{domain}】領域的 {source_lang} 術語翻譯為 {target_lang}。
文件摘要：{document_context}

規則：
1. 根據 context 欄位判斷詞義，避免歧義
2. 品牌名稱、型號、縮寫保留原文不翻譯（confidence=1.0）
3. 優先使用目標語言業界標準術語，避免逐字直譯
4. 輸出嚴格符合 JSON，不加任何說明

術語列表：
{terms_json}

輸出格式：
{{"translations": [{{"source": "...", "target": "...", "confidence": 0.0}}]}}"""


class TermExtractor:
    """Extract and translate terminology using the local Qwen model."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        base_url: str = OLLAMA_BASE_URL,
        timeout: Optional[TimeoutConfig] = None,
        log: Callable[[str], None] = lambda s: None,
    ) -> None:
        self.model = model
        self.base_url = base_url
        self.timeout = timeout or TimeoutConfig()
        self.log = log

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_from_segments(
        self, segments: List[str], domain: str
    ) -> List[Dict]:
        """Call Qwen extraction prompt on each segment, deduplicate, and return candidates."""
        all_terms: Dict[str, Dict] = {}  # keyed by lower(term) for dedup
        total = len(segments)

        for idx, segment in enumerate(segments, 1):
            segment = segment.strip()
            if not segment:
                continue
            self.log(f"[PHASE0] Extracting terms from segment {idx}/{total}")
            prompt = _EXTRACTION_PROMPT_TEMPLATE.format(
                domain=domain,
                segment_text=segment,
            )
            try:
                raw = self._call(prompt)
                candidates = _parse_json_list(raw)
                for c in candidates:
                    term = (c.get("term") or "").strip()
                    if not term:
                        continue
                    key = term.lower()
                    if key not in all_terms:
                        all_terms[key] = {"term": term, "context": c.get("context", "")[:30]}
            except Exception as exc:
                logger.warning("[PHASE0] Extraction failed for segment %d: %s", idx, exc)
                self.log(f"[PHASE0] Segment {idx} extraction error: {exc}")

        return list(all_terms.values())

    def translate_unknown(
        self,
        terms: List[Dict],
        source_lang: str,
        target_lang: str,
        domain: str,
        document_context: str = "",
    ) -> List[Dict]:
        """Translate unknown terms via Qwen and return [{source, target, confidence}]."""
        if not terms:
            return []

        terms_json = json.dumps(
            [{"term": t["term"], "context": t.get("context", "")} for t in terms],
            ensure_ascii=False,
        )
        prompt = _TRANSLATION_PROMPT_TEMPLATE.format(
            domain=domain,
            source_lang=source_lang,
            target_lang=target_lang,
            document_context=(document_context or "").strip()[:300],
            terms_json=terms_json,
        )
        self.log(f"[PHASE0] Translating {len(terms)} unknown terms → {target_lang}")
        try:
            raw = self._call(prompt)
            return _parse_translation_response(raw)
        except Exception as exc:
            logger.warning("[PHASE0] Term translation failed: %s", exc)
            self.log(f"[PHASE0] Term translation error: {exc}")
            return []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _call(self, prompt: str) -> str:
        """Send a prompt to Ollama and return the text response."""
        import requests

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "think": False,
            "options": {"temperature": 0.1, "top_p": 0.9, "top_k": 40},
        }
        connect_t, read_t = self.timeout.get_timeout_tuple()
        resp = requests.post(
            f"{self.base_url.rstrip('/')}/api/generate",
            json=payload,
            stream=True,
            timeout=(connect_t, read_t),
        )
        resp.raise_for_status()

        parts: List[str] = []
        try:
            for line in resp.iter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                token = data.get("response", "")
                if token:
                    parts.append(token)
                if data.get("done", False):
                    break
        finally:
            resp.close()

        raw = "".join(parts).strip()
        # Strip Qwen3.5 <think> blocks
        result = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
        return result

    def unload(self) -> None:
        """Unload Qwen from VRAM via keep_alive=0."""
        import requests

        self.log(f"[PHASE0] Unloading model {self.model} (keep_alive=0)")
        try:
            payload = {"model": self.model, "prompt": "", "keep_alive": 0, "options": {"num_gpu": 99}}
            connect_t, read_t = self.timeout.get_timeout_tuple()
            resp = requests.post(
                f"{self.base_url.rstrip('/')}/api/generate",
                json=payload,
                timeout=(connect_t, read_t),
            )
            if resp.status_code == 200:
                self.log("[PHASE0] Qwen unloaded from VRAM")
            else:
                self.log(f"[PHASE0] Unload returned HTTP {resp.status_code}")
        except Exception as exc:
            self.log(f"[PHASE0] Unload error (non-fatal): {exc}")
            logger.warning("[PHASE0] Unload error: %s", exc)


# ------------------------------------------------------------------
# Parsing helpers
# ------------------------------------------------------------------

def _robust_loads(text: str):
    """Parse JSON with json_repair when available, fall back to stdlib."""
    if _HAS_JSON_REPAIR:
        return _repair_json(text, return_objects=True)
    # Fallback: try raw json.loads (may still fail on malformed output)
    return json.loads(text)


def _parse_json_list(text: str) -> List[Dict]:
    """Extract a JSON array from model output, using json_repair when available."""
    text = text.strip()
    try:
        parsed = _robust_loads(text)
        if isinstance(parsed, list):
            return [d for d in parsed if isinstance(d, dict)]
        # json_repair may wrap a lone array as a dict in edge cases — unwrap
        if isinstance(parsed, dict) and len(parsed) == 1:
            inner = next(iter(parsed.values()))
            if isinstance(inner, list):
                return [d for d in inner if isinstance(d, dict)]
    except Exception:
        # Last-resort: try regex extraction before giving up
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(0))
                if isinstance(parsed, list):
                    return [d for d in parsed if isinstance(d, dict)]
            except Exception:
                pass
    logger.warning("[PHASE0] Failed to parse extraction JSON: %r", text[:200])
    return []


def _parse_translation_response(text: str) -> List[Dict]:
    """Parse {'translations': [{source, target, confidence}]} from model output."""
    text = text.strip()
    try:
        parsed = _robust_loads(text)
        if isinstance(parsed, dict):
            translations = parsed.get("translations", [])
            if isinstance(translations, list):
                return [
                    {
                        "source": str(t.get("source", "")),
                        "target": str(t.get("target", "")),
                        "confidence": float(t.get("confidence", 1.0)),
                    }
                    for t in translations
                    if isinstance(t, dict) and t.get("source")
                ]
    except Exception:
        # Last-resort fallback
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(0))
                if isinstance(parsed, dict):
                    translations = parsed.get("translations", [])
                    return [
                        {
                            "source": str(t.get("source", "")),
                            "target": str(t.get("target", "")),
                            "confidence": float(t.get("confidence", 1.0)),
                        }
                        for t in translations
                        if isinstance(t, dict) and t.get("source")
                    ]
            except Exception:
                pass
    logger.warning("[PHASE0] Failed to parse translation JSON: %r", text[:200])
    return []


def run_phase0(
    segments: List[str],
    source_lang: str,
    target_lang: str,
    scenario: str,
    document_context: str,
    term_db: TermDB,
    model: str = DEFAULT_MODEL,
    base_url: str = OLLAMA_BASE_URL,
    timeout: Optional[TimeoutConfig] = None,
    log: Callable[[str], None] = lambda s: None,
) -> Dict:
    """Run Phase 0 end-to-end: extract → filter → translate → write DB → unload.

    Returns a term_summary dict: {extracted, skipped, added}.
    Always unloads the model. On failure, returns current DB terms still usable.
    """
    domain = SCENARIO_TO_DOMAIN.get(scenario, "general")
    extractor = TermExtractor(model=model, base_url=base_url, timeout=timeout, log=log)

    extracted_count = 0
    skipped_count = 0
    added_count = 0

    try:
        log(f"[PHASE0] Starting term extraction (domain={domain}, model={model})")

        # 1. Extract candidates from all segments
        candidates = extractor.extract_from_segments(segments, domain)
        extracted_count = len(candidates)
        log(f"[PHASE0] Extracted {extracted_count} unique term candidates")

        # 2. Filter already-known terms
        unknown = term_db.get_unknown(candidates, target_lang, domain)
        skipped_count = extracted_count - len(unknown)
        log(f"[PHASE0] {skipped_count} already in DB, {len(unknown)} unknown")

        # 3. Translate unknown terms
        if unknown:
            translations = extractor.translate_unknown(
                unknown,
                source_lang=source_lang,
                target_lang=target_lang,
                domain=domain,
                document_context=document_context,
            )

            # 4. Write to DB
            for t in translations:
                src = t.get("source", "")
                tgt = t.get("target", "")
                conf = t.get("confidence", 1.0)
                if not src or not tgt:
                    continue
                # Find context_snippet from candidates
                ctx = next(
                    (c.get("context", "") for c in candidates if c.get("term") == src),
                    "",
                )
                term = Term(
                    source_text=src,
                    target_text=tgt,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    domain=domain,
                    context_snippet=ctx,
                    confidence=conf,
                    usage_count=0,
                )
                result = term_db.insert(term, strategy="skip")
                if result == "inserted":
                    added_count += 1
                else:
                    skipped_count += 1

        log(f"[PHASE0] Done: extracted={extracted_count}, skipped={skipped_count}, added={added_count}")

    except Exception as exc:
        logger.warning("[PHASE0] Phase 0 failed, continuing with existing DB: %s", exc)
        log(f"[PHASE0] Warning: extraction failed ({exc}), continuing with existing DB terms")
    finally:
        extractor.unload()

    return {"extracted": extracted_count, "skipped": skipped_count, "added": added_count}
