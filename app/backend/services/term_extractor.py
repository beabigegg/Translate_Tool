"""Phase 0 terminology extraction and translation.

Normal (translation) mode uses a DB-first, embedding-gated flow over the PANJIT
cloud endpoint.  ``extraction_only`` mode retains the original Ollama extraction
path unchanged (AC-7 / out of scope for term-extraction-db-first).
"""

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

from app.backend.config import (
    DEFAULT_MODEL,
    OLLAMA_BASE_URL,
    TERM_EMBEDDING_MODEL,
    TERM_EMBEDDING_THRESHOLD,
    TERM_EXTRACTION_MODEL,
    TimeoutConfig,
)
from app.backend.models.term import Term
from app.backend.services.term_db import TermDB

logger = logging.getLogger(__name__)

_LLM_CONFIDENCE_CAP = 0.85

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
包含：品牌名稱、完整型號名稱、設備名稱、製程術語、動作術語、品質術語、行業縮寫（如 SPC、FMEA、ESD）。
注意：
- 型號名稱必須完整提取，例如「SMD C MAX」不要拆成「C MAX」
- 代號+版本應完整提取，例如「OR128 A1」不要拆成「OR128」和「A1」
排除（非常重要，以下項目絕對不要提取）：
- 一般動詞、形容詞、介詞
- 數值、規格值、帶單位的數字（如 100mm、±0.5、65±30g、4~6kg/cm2、3ΦAC 380V、60A、30～60cm）
- 文件編號、表單編號、版本號（如 SOP-001、Rev.1、Form-A、QC-OC063、F-QC1077、W-RD2228）
- 版次代號（如 A0、A1、B0、B1、C0、D2）
- 料號、品號（如 P/N: xxxxx）
- 純代碼縮寫（如 OK、N/A、TBD）
- 登入相關的欄位名稱（如 username、password、panjit 帳號）

輸出格式為 JSON array，不要任何額外說明：
[{{"term": "...", "context": "...（包含該術語的完整短語，20字以內）"}}, ...]

文本：
{segment_text}"""

_TRANSLATION_PROMPT_TEMPLATE = """\
你是專業術語翻譯員。將以下【{domain}】領域的 {source_lang} 術語翻譯為 {target_lang}。
文件摘要：{document_context}

規則：
1. 根據 context 欄位判斷詞義，避免歧義
2. 以下類型必須保留原文不翻譯，設 confidence=1.0：
   - 品牌名稱（如 Panjit、SMD Clip）
   - 型號名稱（如 SMD-C MAX、OR128 A1、Mfm1200L）
   - 行業縮寫（如 SPC、FMEA、ESD、IPQC、FQC、IQC）
   - 軟體名稱（如 SD2000、Ins-M、DigitalCameraViewer）
   - 部門代碼（如 RD、MF、RM、QE、PE）
3. 技術術語應使用目標語言的業界標準翻譯，不要逐字直譯
4. 翻譯結果不可混入原文語言的文字（例如越南文翻譯不可夾雜中文字）
5. 每個 source 必須有對應的 target，不可遺漏
6. 輸出嚴格符合 JSON，不加任何說明

術語列表：
{terms_json}

輸出格式：
{{"translations": [{{"source": "...", "target": "...", "confidence": 0.0}}]}}"""


# Regex patterns for post-extraction filtering (things the LLM might still extract)
_SKIP_PATTERNS = [
    # Pure numeric values, specs, ranges (65±30g, 4~6kg/cm2, 3ΦAC 380V, 60A, 30～60cm)
    # Require numeric part ≥2 chars OR unit part ≥2 chars to avoid killing "5S"
    re.compile(r'^[\d.,±~～<>≤≥]{2,}\s*[a-zA-Zμµ°Φ/%²³]*$'),
    re.compile(r'^[\d.,±~～<>≤≥]+\s*[a-zA-Zμµ°Φ/%²³]{2,}$'),
    # Numeric with units (100mm, 0.5mm)
    re.compile(r'^\d+[\d.,]*\s*(mm|cm|um|μm|µm|kg|g|V|A|Hz|HZ|℃|°C|MPa|ppm)\b', re.IGNORECASE),
    # Spec ranges like "4~6kg/cm2", "3ΦAC 380V 50HZ 60A"
    re.compile(r'^\d+[~～]\d+\s*\w+'),  # 4~6kg/cm2
    re.compile(r'^\d.*[VvAa]\s*$'),
    re.compile(r'^\d+[ΦΦ]'),
    # Version codes (A0, A1, B0, B1, C0, D2) — single letter + single digit, but NOT industry terms like 5S
    re.compile(r'^[A-D]\d$'),
    # Document numbers (QC-OC063, F-QC1077, W-RD2228, RD-OC019)
    re.compile(r'^[A-Z]{1,3}-[A-Z]{1,4}\d{2,}', re.IGNORECASE),
    # Login field names
    re.compile(r'^(username|usename|password|panjit)$', re.IGNORECASE),
    # Single characters or purely whitespace
    re.compile(r'^.?$'),
    # Profiling stopped / UI messages
    re.compile(r'^Profiling\s', re.IGNORECASE),
]


def _should_skip_term(term: str) -> bool:
    """Return True if a candidate term should be filtered out."""
    for pat in _SKIP_PATTERNS:
        if pat.search(term):
            return True
    return False


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
                    if _should_skip_term(term):
                        continue
                    key = term.lower()
                    if key not in all_terms:
                        all_terms[key] = {"term": term, "context": c.get("context", "")[:60]}
            except Exception as exc:
                logger.warning("[PHASE0] Extraction failed for segment %d: %s", idx, exc)
                self.log(f"[PHASE0] Segment {idx} extraction error: {exc}")

        return list(all_terms.values())

    _TRANSLATE_BATCH_SIZE = 25  # Max terms per translation call to avoid output truncation

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

        all_translations: List[Dict] = []
        batch_size = self._TRANSLATE_BATCH_SIZE
        total_batches = (len(terms) + batch_size - 1) // batch_size

        for batch_idx in range(total_batches):
            batch = terms[batch_idx * batch_size : (batch_idx + 1) * batch_size]
            terms_json = json.dumps(
                [{"term": t["term"], "context": t.get("context", "")} for t in batch],
                ensure_ascii=False,
            )
            prompt = _TRANSLATION_PROMPT_TEMPLATE.format(
                domain=domain,
                source_lang=source_lang,
                target_lang=target_lang,
                document_context=(document_context or "").strip()[:300],
                terms_json=terms_json,
            )
            self.log(
                f"[PHASE0] Translating batch {batch_idx + 1}/{total_batches} "
                f"({len(batch)} terms) → {target_lang}"
            )
            try:
                raw = self._call(prompt)
                batch_results = _parse_translation_response(raw)
                all_translations.extend(batch_results)
            except Exception as exc:
                logger.warning(
                    "[PHASE0] Term translation batch %d/%d failed: %s",
                    batch_idx + 1, total_batches, exc,
                )
                self.log(f"[PHASE0] Batch {batch_idx + 1} translation error: {exc}")

        return all_translations

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
            "options": {"temperature": 0.1, "top_p": 0.9, "top_k": 40, "num_ctx": 4096},
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
                        "confidence": min(float(t.get("confidence", 1.0)), _LLM_CONFIDENCE_CAP),
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
                            "confidence": min(float(t.get("confidence", 1.0)), _LLM_CONFIDENCE_CAP),
                        }
                        for t in translations
                        if isinstance(t, dict) and t.get("source")
                    ]
            except Exception:
                pass
    logger.warning("[PHASE0] Failed to parse translation JSON: %r", text[:200])
    return []


class _PANJITTermExtractor:
    """Term extraction/translation using PANJIT chat completions.

    Used by run_phase0_multi on DB miss to call the lightweight extraction
    LLM (gemma4:latest) and the translation LLM via the OpenAI-compatible API.
    Shares prompt templates and parsing helpers with TermExtractor.
    """

    _TRANSLATE_BATCH_SIZE = 25

    def __init__(
        self,
        panjit_client,  # OpenAICompatibleClient instance
        extraction_model: str,
        timeout: Optional[TimeoutConfig] = None,
        log: Callable[[str], None] = lambda s: None,
    ) -> None:
        self._client = panjit_client
        self._extraction_model = extraction_model
        self.log = log
        self.timeout = timeout or TimeoutConfig()

    def _call(self, prompt: str) -> str:
        """Call PANJIT /v1/chat/completions and return text content."""
        # Temporarily override the client model for extraction calls.
        original_model = self._client.model
        self._client.model = self._extraction_model
        try:
            ok, text = self._client._post_completion(prompt)
            if not ok:
                raise RuntimeError(f"PANJIT extraction call failed: {text}")
            return text
        finally:
            self._client.model = original_model

    def extract_from_segments(
        self, segments: List[str], domain: str
    ) -> List[Dict]:
        """Extract terms from segments via PANJIT LLM."""
        all_terms: Dict[str, Dict] = {}
        total = len(segments)
        for idx, segment in enumerate(segments, 1):
            segment = segment.strip()
            if not segment:
                continue
            self.log(f"[PHASE0] Extracting terms from segment {idx}/{total} via PANJIT")
            prompt = _EXTRACTION_PROMPT_TEMPLATE.format(
                domain=domain,
                segment_text=segment,
            )
            try:
                raw = self._call(prompt)
                for c in _parse_json_list(raw):
                    term = (c.get("term") or "").strip()
                    if not term or _should_skip_term(term):
                        continue
                    key = term.lower()
                    if key not in all_terms:
                        all_terms[key] = {"term": term, "context": c.get("context", "")[:60]}
            except Exception as exc:
                logger.warning("[PHASE0] PANJIT extraction failed for segment %d: %s", idx, exc)
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
        """Translate unknown terms via PANJIT LLM."""
        if not terms:
            return []
        all_translations: List[Dict] = []
        batch_size = self._TRANSLATE_BATCH_SIZE
        total_batches = (len(terms) + batch_size - 1) // batch_size
        for batch_idx in range(total_batches):
            batch = terms[batch_idx * batch_size : (batch_idx + 1) * batch_size]
            terms_json = json.dumps(
                [{"term": t["term"], "context": t.get("context", "")} for t in batch],
                ensure_ascii=False,
            )
            prompt = _TRANSLATION_PROMPT_TEMPLATE.format(
                domain=domain,
                source_lang=source_lang,
                target_lang=target_lang,
                document_context=(document_context or "").strip()[:300],
                terms_json=terms_json,
            )
            self.log(
                f"[PHASE0] Translating batch {batch_idx + 1}/{total_batches} "
                f"({len(batch)} terms) → {target_lang} via PANJIT"
            )
            try:
                raw = self._call(prompt)
                all_translations.extend(_parse_translation_response(raw))
            except Exception as exc:
                logger.warning(
                    "[PHASE0] PANJIT translation batch %d/%d failed: %s",
                    batch_idx + 1, total_batches, exc,
                )
                self.log(f"[PHASE0] Batch {batch_idx + 1} translation error: {exc}")
        return all_translations


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
    """Run Phase 0 for a single target language (backward-compat wrapper)."""
    return run_phase0_multi(
        segments=segments,
        source_lang=source_lang,
        target_langs=[target_lang],
        scenario=scenario,
        document_context=document_context,
        term_db=term_db,
        model=model,
        base_url=base_url,
        timeout=timeout,
        log=log,
    )


def run_phase0_multi(
    segments: List[str],
    source_lang: str,
    target_langs: List[str],
    scenario: str,
    document_context: str,
    term_db: TermDB,
    # Legacy Ollama params — used only for extraction_only mode (AC-7, out of scope).
    model: str = DEFAULT_MODEL,
    base_url: str = OLLAMA_BASE_URL,
    timeout: Optional[TimeoutConfig] = None,
    log: Callable[[str], None] = lambda s: None,
    # PANJIT DB-first params — when provided, switches to the new embedding-gated flow.
    panjit_base_url: Optional[str] = None,
    panjit_api_key: str = "",
    panjit_tls_verify: bool = False,
    embedding_model: str = TERM_EMBEDDING_MODEL,
    extraction_model: str = TERM_EXTRACTION_MODEL,
    embedding_threshold: float = TERM_EMBEDDING_THRESHOLD,
) -> Dict:
    """Run Phase 0 for multiple target languages.

    When PANJIT params are provided (panjit_base_url is not None): uses the
    DB-first embedding-gated flow — embed segments via PANJIT, cosine-match
    against DB terms, inject hits without an extraction LLM call; only calls
    the PANJIT extraction LLM on DB miss (BR-62).  Embedding-API failure is
    non-fatal: skips injection, returns with empty extracted_source_texts so
    translation continues (design.md "Embedding failure → skip injection").

    When panjit_base_url is None (legacy/extraction_only path): falls back to
    the original Ollama LLM extraction flow (AC-7).

    Returns a term_summary dict: {extracted, skipped, added, extracted_source_texts}.
    """
    if not target_langs:
        target_langs = ["English"]

    domain = SCENARIO_TO_DOMAIN.get(scenario, "general")

    extracted_count = 0
    skipped_count = 0
    added_count = 0
    candidates: List[Dict] = []

    # -----------------------------------------------------------------------
    # DB-FIRST PATH (PANJIT embedding-gated flow)
    # -----------------------------------------------------------------------
    if panjit_base_url is not None:
        from app.backend.clients.openai_compatible_client import OpenAICompatibleClient

        panjit_client = OpenAICompatibleClient(
            base_url=panjit_base_url,
            api_key=panjit_api_key,
            model=extraction_model,
            provider_id="panjit-term",
            verify_ssl=panjit_tls_verify,
        )

        try:
            log(
                f"[PHASE0] DB-first flow (domain={domain}, "
                f"embed_model={embedding_model}, "
                f"extract_model={extraction_model}, "
                f"threshold={embedding_threshold}, "
                f"targets={target_langs})"
            )

            # 1. Embed source segments via PANJIT.
            non_empty_segments = [s.strip() for s in segments if s.strip()]
            if not non_empty_segments:
                log("[PHASE0] No non-empty segments; skipping.")
                return {
                    "extracted": 0,
                    "skipped": 0,
                    "added": 0,
                    "extracted_source_texts": [],
                }

            query_vectors = panjit_client.embed(non_empty_segments, model_name=embedding_model)
            if not query_vectors:
                # Embedding API failure — non-fatal, skip injection.
                logger.warning("[PHASE0] Embedding API returned empty; skipping term injection.")
                log("[PHASE0] Warning: embedding API unavailable; skipping term injection.")
                return {
                    "extracted": 0,
                    "skipped": 0,
                    "added": 0,
                    "extracted_source_texts": [],
                }

            # 2. For each target language: cosine-match DB → conditional extraction.
            for target_lang in target_langs:
                # Check DB for similar terms using cosine similarity.
                embed_fn: Callable[[List[str]], List[List[float]]] = (
                    lambda texts: panjit_client.embed(texts, model_name=embedding_model)
                )
                db_hits = term_db.get_similar_terms_by_embedding(
                    query_vectors=query_vectors,
                    target_lang=target_lang,
                    domain=domain,
                    threshold=embedding_threshold,
                    embed_fn=embed_fn,
                )

                if db_hits:
                    # DB hit: inject existing terms, no extraction LLM call.
                    hit_source_texts = [t.source_text for t in db_hits]
                    log(
                        f"[PHASE0] [{target_lang}] DB hit: {len(db_hits)} terms "
                        f"above threshold {embedding_threshold}; skipping extraction."
                    )
                    for t in db_hits:
                        key = t.source_text.lower()
                        if not any(c.get("term", "").lower() == key for c in candidates):
                            candidates.append({"term": t.source_text, "context": t.context_snippet})
                    # Update counts.
                    extracted_count += len(db_hits)
                    skipped_count += len(db_hits)
                else:
                    # DB miss: call PANJIT extraction LLM to mint new terms.
                    log(
                        f"[PHASE0] [{target_lang}] DB miss (no terms above threshold); "
                        f"calling extraction LLM ({extraction_model})."
                    )
                    extractor = _PANJITTermExtractor(
                        panjit_client=panjit_client,
                        extraction_model=extraction_model,
                        timeout=timeout,
                        log=log,
                    )
                    new_candidates = extractor.extract_from_segments(non_empty_segments, domain)
                    extracted_count += len(new_candidates)
                    log(f"[PHASE0] [{target_lang}] Extracted {len(new_candidates)} term candidates via LLM")

                    unknown = term_db.get_unknown(new_candidates, target_lang, domain)
                    lang_skipped = len(new_candidates) - len(unknown)

                    if unknown:
                        translations = extractor.translate_unknown(
                            unknown,
                            source_lang=source_lang,
                            target_lang=target_lang,
                            domain=domain,
                            document_context=document_context,
                        )
                        lang_added = 0
                        for t in translations:
                            src = t.get("source", "")
                            tgt = t.get("target", "")
                            conf = min(float(t.get("confidence", 1.0)), _LLM_CONFIDENCE_CAP)
                            if not src or not tgt:
                                continue
                            ctx = next(
                                (c.get("context", "") for c in new_candidates if c.get("term") == src),
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
                                lang_added += 1
                                candidates.append({"term": src, "context": ctx})
                            else:
                                lang_skipped += 1
                        added_count += lang_added
                        log(f"[PHASE0] [{target_lang}] added={lang_added}")

                    skipped_count += lang_skipped

            log(
                f"[PHASE0] Done: extracted={extracted_count}, "
                f"skipped={skipped_count}, added={added_count}"
            )

        except Exception as exc:
            logger.warning("[PHASE0] DB-first phase 0 failed, continuing with existing DB: %s", exc)
            log(f"[PHASE0] Warning: DB-first extraction failed ({exc}), continuing with existing DB terms")

        return {
            "extracted": extracted_count,
            "skipped": skipped_count,
            "added": added_count,
            "extracted_source_texts": [c["term"] for c in candidates],
        }

    # -----------------------------------------------------------------------
    # LEGACY OLLAMA PATH (extraction_only / fallback)
    # -----------------------------------------------------------------------
    extractor = TermExtractor(model=model, base_url=base_url, timeout=timeout, log=log)

    try:
        log(f"[PHASE0] Starting term extraction (domain={domain}, model={model}, targets={target_langs})")

        # 1. Extract candidates once — language-agnostic
        candidates = extractor.extract_from_segments(segments, domain)
        extracted_count = len(candidates)
        log(f"[PHASE0] Extracted {extracted_count} unique term candidates")

        # 2–4. For each target language: filter → translate → write DB
        for target_lang in target_langs:
            unknown = term_db.get_unknown(candidates, target_lang, domain)
            lang_skipped = extracted_count - len(unknown)
            log(f"[PHASE0] [{target_lang}] {lang_skipped} already in DB, {len(unknown)} unknown")

            if unknown:
                translations = extractor.translate_unknown(
                    unknown,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    domain=domain,
                    document_context=document_context,
                )

                lang_added = 0
                for t in translations:
                    src = t.get("source", "")
                    tgt = t.get("target", "")
                    conf = min(float(t.get("confidence", 1.0)), _LLM_CONFIDENCE_CAP)
                    if not src or not tgt:
                        continue
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
                        lang_added += 1
                    else:
                        lang_skipped += 1

                added_count += lang_added
                log(f"[PHASE0] [{target_lang}] added={lang_added}")

            skipped_count += lang_skipped

        log(f"[PHASE0] Done: extracted={extracted_count}, skipped={skipped_count}, added={added_count}")

    except Exception as exc:
        logger.warning("[PHASE0] Phase 0 failed, continuing with existing DB: %s", exc)
        log(f"[PHASE0] Warning: extraction failed ({exc}), continuing with existing DB terms")
    finally:
        extractor.unload()

    return {
        "extracted": extracted_count,
        "skipped": skipped_count,
        "added": added_count,
        "extracted_source_texts": [c["term"] for c in candidates] if candidates else [],
    }
