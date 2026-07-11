"""
Backend configuration for Translate Tool.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_cfg_logger = logging.getLogger(__name__)


class ModelType(str, Enum):
    """Supported translation model categories."""

    GENERAL = "general"
    TRANSLATION = "translation"

APP_NAME = "Translate Tool"
DEFAULT_MODEL = "qwen3.5:9b"
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_NUM_GPU = int(os.environ.get("OLLAMA_NUM_GPU", "99"))
OLLAMA_KV_CACHE_TYPE = os.environ.get("OLLAMA_KV_CACHE_TYPE", "q4_0")

# Per-type context window with backward-compatible OLLAMA_NUM_CTX fallback.
_OLLAMA_NUM_CTX_RAW = os.environ.get("OLLAMA_NUM_CTX")
GENERAL_NUM_CTX = int(os.environ.get("GENERAL_NUM_CTX") or _OLLAMA_NUM_CTX_RAW or 4096)
TRANSLATION_NUM_CTX = int(os.environ.get("TRANSLATION_NUM_CTX") or _OLLAMA_NUM_CTX_RAW or 3072)
OLLAMA_NUM_CTX = GENERAL_NUM_CTX  # backward-compat alias imported by ollama_client

MODEL_TYPE_OPTIONS: Dict[ModelType, Dict[str, object]] = {
    ModelType.GENERAL: {
        "num_ctx": GENERAL_NUM_CTX,
        "num_gpu": OLLAMA_NUM_GPU,
        "kv_cache_type": OLLAMA_KV_CACHE_TYPE,
        # Greedy decode defaults — benchmark-optimal (March 2026 full-factorial study)
        "temperature": 0.05,
        "top_p": 0.50,
        "top_k": 10,
        "repeat_penalty": 1.0,
        "frequency_penalty": 0.0,
    },
    ModelType.TRANSLATION: {
        "num_ctx": TRANSLATION_NUM_CTX,
        "num_gpu": OLLAMA_NUM_GPU,
        "kv_cache_type": OLLAMA_KV_CACHE_TYPE,
        # Greedy decode defaults — benchmark-optimal (March 2026 full-factorial study)
        "temperature": 0.05,
        "top_p": 0.50,
        "top_k": 10,
        "repeat_penalty": 1.0,
        "frequency_penalty": 0.0,
    },
}

VRAM_METADATA: Dict[ModelType, Dict[str, object]] = {
    ModelType.GENERAL: {
        "model_size_gb": 3.5,
        "kv_per_1k_ctx_gb": 0.35,
        "default_num_ctx": GENERAL_NUM_CTX,
        "min_num_ctx": 1024,
        "max_num_ctx": 8192,
    },
    ModelType.TRANSLATION: {
        "model_size_gb": 5.7,
        "kv_per_1k_ctx_gb": 0.22,
        "default_num_ctx": TRANSLATION_NUM_CTX,
        "min_num_ctx": 1024,
        "max_num_ctx": 8192,
    },
}

DEFAULT_CONNECT_TIMEOUT_S = 10.0
DEFAULT_READ_TIMEOUT_S = 360.0

# OPENAI_COMPLETION_MAX_TOKENS: max_tokens sent to every OpenAICompatibleClient
# completion request (translate + judge). Reasoning models served behind an
# OpenAI-compatible endpoint (e.g. gpt-oss:120b) emit hidden reasoning_content
# before the final content field; with no max_tokens the provider's own default
# cap can be exhausted entirely by reasoning, returning finish_reason="length"
# with an EMPTY content field. 4096 was verified sufficient against panjit's
# gpt-oss:120b for judge-length prompts (finish_reason="stop").
OPENAI_COMPLETION_MAX_TOKENS: int = int(os.environ.get("OPENAI_COMPLETION_MAX_TOKENS", "4096"))

# OPENAI_TOTAL_TIMEOUT_SECONDS: wall-clock total-duration ceiling on every
# OpenAICompatibleClient completion (qa-judge-hang-recovery, BR-100). Additive on
# top of the per-chunk (connect, read) timeout tuple — the read timeout only
# bounds the inter-chunk gap, so a provider that dribbles keep-alive bytes can
# otherwise hang forever. On expiry the call degrades (does not crash), matching
# CRITIQUE_TIMEOUT_SECONDS. Positive float seconds; default 480 is a generous
# placeholder above the ~420s worst case of a healthy (120 connect + 300 read)
# call — calibrate for the longest legitimate cloud generation. Set very high to
# effectively disable the ceiling (rollback).
OPENAI_TOTAL_TIMEOUT_SECONDS: float = float(os.environ.get("OPENAI_TOTAL_TIMEOUT_SECONDS", "480"))

API_ATTEMPTS = 3
API_BACKOFF_BASE = 1.6
SENTENCE_MODE = True
INSERT_FONT_SIZE_PT = 10

DEFAULT_BATCH_SIZE = 10
MIN_BATCH_SIZE = 1
MAX_BATCH_SIZE = 50
BATCH_SEPARATOR = "\n---SEGMENT_SEPARATOR---\n"

# Character-based batching (derived from OLLAMA_NUM_CTX)
MAX_MAX_BATCH_CHARS = 100000      # Maximum 100K chars
# Estimate: num_ctx ÷ 2 (reserve output space) × 3 (chars/token conservative) - 1000 (prompt template)
# Floor at 2000 to ensure at least one paragraph can fit
MIN_MAX_BATCH_CHARS = 2000
DEFAULT_MAX_BATCH_CHARS = max(MIN_MAX_BATCH_CHARS, min((OLLAMA_NUM_CTX // 2) * 3 - 1000, MAX_MAX_BATCH_CHARS))

# Translation granularity: "sentence" (legacy) | "paragraph" (recommended for quality)
TRANSLATION_GRANULARITY = "paragraph"
MAX_PARAGRAPH_CHARS = 2000  # Split paragraphs longer than this
MAX_MERGE_SEGMENTS = 4  # Max segments per merged batch (reduced for 4B model to mitigate "Lost in the Middle")
# Sliding context: include N preceding segments as read-only context so the model
# understands the domain without an explicit glossary.  Only the last segment is translated.
CONTEXT_WINDOW_SEGMENTS = 2  # Number of preceding segments to include as context
CONTEXT_MAX_CHARS = 300  # Max total chars for context (truncate if longer)
# Auto-detect document context: sample file text and ask LLM to describe the document
# before translating, then inject the description into the system prompt.
CONTEXT_DETECTION_ENABLED = True
CONTEXT_SAMPLE_CHARS = 500  # Max chars to sample from file for context detection

# DOCX nested-table recursion bound (docx-nested-table-collection, BR-113).
# Hardcoded constant, NOT an env var (mirrors CONTEXT_DETECTION_ENABLED above;
# env-contract.md forbids an env row for this value).
MAX_TABLE_NESTING_DEPTH = 3

# PPTX group-shape recursion bound (pptx-group-shape-collection, BR-116).
# Hardcoded constant, NOT an env var (mirrors MAX_TABLE_NESTING_DEPTH above;
# env-contract.md forbids an env row for this value).
MAX_GROUP_NESTING_DEPTH = 3

# Long-document chunking overlap (p2-long-doc-chunking, BR-47, BR-49)
# Number of tokens of overlap shared between adjacent chunks.
# Must be a positive integer and must be < num_ctx (enforced at chunker init).
# Has no effect when the document fits in one chunk (BR-52).
CHUNK_OVERLAP_TOKENS: int = int(os.environ.get("CHUNK_OVERLAP_TOKENS", "50"))

# Quality Evaluation configuration (p2-comet-qe, BR-54..BR-58; quality-metrics-gating AC-3, AC-4)
# QE_ENABLED: set to "false"/"0" to disable COMET scoring. Default is enabled (true).
# When enabled, the critique loop uses QE as the adoption gate (AC-7); falls back to
# length-ratio heuristic if the COMET library is not installed (AC-8).
QE_ENABLED: bool = os.environ.get("QE_ENABLED", "true").lower() in ("true", "1")
QE_MODEL_NAME: str = os.environ.get("QE_MODEL_NAME", "Unbabel/wmt22-cometkiwi-da")
QE_DEVICE: str = os.environ.get("QE_DEVICE", "cpu")

# Critique loop configuration (p2-prompt-fewshot-glossary, BR-44)
CRITIQUE_LOOP_ENABLED: bool = os.environ.get("CRITIQUE_LOOP_ENABLED", "1").lower() in ("1", "true", "yes")
CRITIQUE_MAX_ITERATIONS: int = int(os.environ.get("CRITIQUE_MAX_ITERATIONS", "3"))
CRITIQUE_TIMEOUT_SECONDS: float = float(os.environ.get("CRITIQUE_TIMEOUT_SECONDS", "60"))

# JSON-structured translation I/O (json-structured-translation-io, BR-79..BR-83,
# BR-111, BR-112). Kill switch: when false, both the table and body paths use the
# legacy Markdown pipe-grid / plain-text pipeline unconditionally (Resolution A).
# Read as `config.JSON_STRUCTURED_TRANSLATION_ENABLED` (module-attribute access) at
# every call site, NEVER via `from app.backend.config import ...` — the import-bound
# form freezes the value at first import and defeats `monkeypatch.setattr(config, ...)`
# in tests (see CRITIQUE_LOOP_ENABLED above for the pattern to avoid).
JSON_STRUCTURED_TRANSLATION_ENABLED: bool = os.environ.get(
    "JSON_STRUCTURED_TRANSLATION_ENABLED", "1"
).lower() in ("1", "true", "yes")

# Few-shot example injection (p2-prompt-fewshot-glossary, BR-42)
# When enabled, build_strategy() appends scenario-specific source→target example
# pairs into the system prompt so every translation call carries ≥1 few-shot pair.
FEWSHOT_INJECTION_ENABLED: bool = os.environ.get("FEWSHOT_INJECTION_ENABLED", "1").lower() in ("1", "true", "yes")

# Dynamic scenario strategy:
# - Detect translation scenario from filename/sample/context
# - Apply scenario-specific decoding options
# - Isolate cache keys per scenario variant to avoid cross-scenario contamination
DYNAMIC_SCENARIO_STRATEGY_ENABLED = os.environ.get("DYNAMIC_SCENARIO_STRATEGY_ENABLED", "1").lower() in ("1", "true", "yes")
QWEN_CONTEXT_FLOW_ENABLED = os.environ.get("QWEN_CONTEXT_FLOW_ENABLED", "1").lower() in ("1", "true", "yes")
SCENARIO_CACHE_VARIANT_ENABLED = os.environ.get("SCENARIO_CACHE_VARIANT_ENABLED", "1").lower() in ("1", "true", "yes")

EXCEL_FORMULA_MODE = "skip"
MAX_SHAPE_CHARS = 1200

# PDF parsing configuration
PDF_PARSER_ENGINE = "pymupdf"  # pymupdf | pypdf2 (fallback)
PDF_SKIP_HEADER_FOOTER = False  # Skip header/footer translation
PDF_HEADER_FOOTER_MARGIN_PT = 50  # Margin for header/footer detection (points)

# Layout detector configuration (p2-layout-detection)
# LAYOUT_DETECTOR_MODEL_PATH: optional explicit path to heron-101 ONNX weights directory.
# When unset, falls back to HuggingFace cache / auto-download (D-5, tier 2/3).
LAYOUT_DETECTOR_MODEL_PATH: Optional[str] = os.environ.get("LAYOUT_DETECTOR_MODEL_PATH") or None
# LAYOUT_DETECTOR_ENABLED: default on; set to "0"/"false"/"no" to revert to heuristic.
LAYOUT_DETECTOR_ENABLED: bool = os.environ.get("LAYOUT_DETECTOR_ENABLED", "true").lower() in ("1", "true", "yes")

# Layout-QA safety net (layout-qa-safety-net, BR-106). Default OFF: when
# false, no output-side layout-QA pass runs after a PDF render; rendered
# output and job behavior are byte-for-byte unchanged. Set to "1"/"true"/"yes"
# to enable the fail-soft post-render BIoU-regression + residual-source-text
# check via run_layout_qa() (PDF->PDF path only).
LAYOUT_QA_ENABLED: bool = os.environ.get("LAYOUT_QA_ENABLED", "false").lower() in ("1", "true", "yes")
# LAYOUT_QA_MAX_BOXES_PER_PAGE: performance short-circuit for the layout-QA
# pass (BR-106) -- a page whose source or rendered box count exceeds this
# value is skipped from BIoU matching (and logged), bounding the per-page
# O(source_boxes x rendered_boxes) matching cost. Ignored when
# LAYOUT_QA_ENABLED=false.
LAYOUT_QA_MAX_BOXES_PER_PAGE: int = int(os.getenv("LAYOUT_QA_MAX_BOXES_PER_PAGE", "500"))

# PDF rasterisation DPI for layout detector (pdf-layout-refactor, AC-6, D-6)
# Higher DPI improves detector classification quality; 150 is the balanced default.
# Set PDF_RENDER_DPI=72 to reproduce the previous 72-DPI behaviour.
PDF_RENDER_DPI: int = int(os.getenv("PDF_RENDER_DPI", "150"))

# OCR backend for scanned PDFs (pdf-layout-refactor, AC-7, D-7)
# Default disabled (False): lazy-import seam; no hard dependency on surya/paddleocr.
# Set OCR_ENABLED=true to route near-empty pages through ocr_backend.run_ocr().
OCR_ENABLED: bool = os.getenv("OCR_ENABLED", "false").lower() in ("1", "true", "yes")

# Bounded local table-row-growth pre-pass (pdf-text-overflow-fix, AC-10, BR-103,
# ADR-0013). Default ON. Set to "0"/"false"/"no" as a production kill-switch for
# the HIGH-risk overlay-mode background-collision case (a grown row's translated
# text can cross the original source PDF's table rule lines in overlay mode,
# since the pre-pass shifts only text/whitening, not the preserved background
# graphics). Gates ONLY the AC-10 row-growth pre-pass; AC-9/AC-11 and all other
# fixes in this change stay unconditional.
PDF_TABLE_ROW_GROWTH_ENABLED: bool = os.getenv("PDF_TABLE_ROW_GROWTH_ENABLED", "true").lower() in ("1", "true", "yes")

# Table recognition configuration (p3-table-structure)
# TABLE_RECOGNITION_MODEL_PATH: optional explicit path to TATR/TableFormer ONNX weights directory.
# When unset, falls back to HuggingFace cache / auto-download (D-5, tier 2/3).
TABLE_RECOGNITION_MODEL_PATH: Optional[str] = os.environ.get("TABLE_RECOGNITION_MODEL_PATH") or None
# TABLE_RECOGNITION_ENABLED: default off until weights are validated (BR-71).
# Set to "1"/"true"/"yes" to enable. PDF-only scope (p3-table-structure).
TABLE_RECOGNITION_ENABLED: bool = os.environ.get("TABLE_RECOGNITION_ENABLED", "false").lower() in ("1", "true", "yes")

# LLM-as-judge configuration (p3-llm-judge, BR-72..BR-77)
# JUDGE_ENABLED: set to "true"/"1"/"yes" to activate Gemma judge scoring after each job.
# Default is disabled (false) so no extra Gemma call is made at startup.
JUDGE_ENABLED: bool = os.environ.get("JUDGE_ENABLED", "false").lower() in ("1", "true", "yes")
# JUDGE_PROVIDER: "ollama" (default, local) or "cloud" (routes the text evaluate()
# pass through the configured cloud provider, e.g. panjit, via providers.yml).
# judge_layout() ALWAYS uses a dedicated local Ollama client regardless of this
# setting — page images must never leave the process (BR-95 / ADR 0008).
JUDGE_PROVIDER: str = os.environ.get("JUDGE_PROVIDER", "ollama").strip().lower()
# JUDGE_MODEL: model name for the text evaluate() pass. Ollama model name when
# JUDGE_PROVIDER="ollama" (D4 default); cloud provider's model name when
# JUDGE_PROVIDER="cloud" (e.g. "gpt-oss:120b" for panjit — gemma3 is Ollama-only).
JUDGE_MODEL: str = os.environ.get("JUDGE_MODEL", "gemma3")
# JUDGE_LAYOUT_MODEL: local Ollama model name dedicated to judge_layout() image
# scoring. Always local, independent of JUDGE_PROVIDER (BR-95 / ADR 0008).
JUDGE_LAYOUT_MODEL: str = os.environ.get("JUDGE_LAYOUT_MODEL", "gemma3")
# JUDGE_CLOUD_PROVIDER_ID: which providers.yml provider id to use when
# JUDGE_PROVIDER="cloud" (defaults to "panjit").
JUDGE_CLOUD_PROVIDER_ID: str = os.environ.get("JUDGE_CLOUD_PROVIDER_ID", "panjit")
# JUDGE_MAX_ITERATIONS: maximum re-translation iterations when score is 中 or 低 (BR-73).
JUDGE_MAX_ITERATIONS: int = int(os.environ.get("JUDGE_MAX_ITERATIONS", "3"))

# Layout preservation configuration
LAYOUT_PRESERVATION_MODE = "inline"  # inline | overlay | side_by_side
DEFAULT_FONT_FAMILY = "NotoSansSC"  # Default font for PDF rendering
MIN_READABLE_FONT_PT: int = 8  # Readable floor for fit cascade (AC-3, BR-85, BR-88)
MIN_FONT_SIZE_PT = MIN_READABLE_FONT_PT  # alias; was 6 — reconciled to 8 (D-3)
MAX_FONT_SIZE_PT = 72  # Maximum font size
FONT_SIZE_SHRINK_FACTOR = 0.9  # Shrink factor for font scaling
PDF_DRAW_MASK = True  # Draw white mask over original text in overlay mode (set False for transparent background)
PDF_MASK_MARGIN_PT = 0.5  # Margin for white mask to preserve table borders (points)
PDF_SHOW_MISSING_PLACEHOLDER = True  # Show placeholder text for missing translations

# Language-aware font size configuration
# Each language can have different max/min font sizes and height ratio
FONT_SIZE_CONFIG = {
    "default": {"max": 11, "min": 4, "height_ratio": 0.75, "shrink_factor": 0.88},
    "zh-tw": {"max": 12, "min": 6, "height_ratio": 0.70, "shrink_factor": 0.85},
    "zh-cn": {"max": 12, "min": 6, "height_ratio": 0.70, "shrink_factor": 0.85},
    "ja": {"max": 12, "min": 6, "height_ratio": 0.70, "shrink_factor": 0.85},
    "ko": {"max": 12, "min": 6, "height_ratio": 0.70, "shrink_factor": 0.85},
    "th": {"max": 11, "min": 5, "height_ratio": 0.72, "shrink_factor": 0.88},
    "ar": {"max": 13, "min": 6, "height_ratio": 0.65, "shrink_factor": 0.88},
    "he": {"max": 13, "min": 6, "height_ratio": 0.65, "shrink_factor": 0.88},
    "vi": {"max": 11, "min": 5, "height_ratio": 0.73, "shrink_factor": 0.88},
}

# Document size limits (set to very high values to effectively disable limits)
MAX_SEGMENTS = 10_000_000  # 10 million segments
MAX_TEXT_LENGTH = 1_000_000_000  # 1 billion characters (effectively unlimited)

# Performance: Job management
MAX_JOBS_IN_MEMORY = int(os.environ.get("MAX_JOBS_IN_MEMORY", "100"))
JOB_TTL_HOURS = int(os.environ.get("JOB_TTL_HOURS", "24"))
CLEANUP_INTERVAL_MINUTES = int(os.environ.get("CLEANUP_INTERVAL_MINUTES", "30"))

# Performance: HTTP connection pool
HTTP_POOL_CONNECTIONS = int(os.environ.get("HTTP_POOL_CONNECTIONS", "2"))
HTTP_POOL_MAXSIZE = int(os.environ.get("HTTP_POOL_MAXSIZE", "5"))

ENV_CONNECT_TIMEOUT = "TRANSLATE_CONNECT_TIMEOUT"
ENV_READ_TIMEOUT = "TRANSLATE_READ_TIMEOUT"

# LibreOffice headless conversion for legacy .doc/.xls
LIBREOFFICE_PATH = os.environ.get("LIBREOFFICE_PATH", "")  # Empty = auto-detect
LIBREOFFICE_TIMEOUT = int(os.environ.get("LIBREOFFICE_TIMEOUT", "120"))

VERIFY_MAX_RETRIES = 2  # Retries per failed segment during post-translation verification

# Term injection gate: optional loose mode
TERM_INJECT_HIGH_CONFIDENCE_UNVERIFIED: bool = os.getenv("TERM_INJECT_HIGH_CONFIDENCE_UNVERIFIED", "false").lower() == "true"
TERM_INJECT_CONF_THRESHOLD: float = float(os.getenv("TERM_INJECT_CONF_THRESHOLD", "0.9"))

# DB-first term extraction configuration (term-extraction-db-first, BR-62)
TERM_EMBEDDING_MODEL: str = os.environ.get("TERM_EMBEDDING_MODEL", "Qwen3-Embedding-8B")
TERM_EMBEDDING_THRESHOLD: float = float(os.environ.get("TERM_EMBEDDING_THRESHOLD", "0.75"))
TERM_EXTRACTION_MODEL: str = os.environ.get("TERM_EXTRACTION_MODEL", "gemma4:latest")

SUPPORTED_EXTENSIONS = {".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls", ".pdf"}

LANG_CODE_MAP = {
    # East Asian
    "English": ("English", "en"),
    "Traditional Chinese": ("Traditional Chinese", "zh-TW"),
    "Simplified Chinese": ("Simplified Chinese", "zh-CN"),
    "Japanese": ("Japanese", "ja"),
    "Korean": ("Korean", "ko"),
    # Southeast Asian
    "Vietnamese": ("Vietnamese", "vi"),
    "Thai": ("Thai", "th"),
    "Indonesian": ("Indonesian", "id"),
    "Malay": ("Malay", "ms"),
    "Filipino": ("Filipino", "fil"),
    "Burmese": ("Burmese", "my"),
    "Khmer": ("Khmer", "km"),
    "Lao": ("Lao", "lo"),
    # South Asian
    "Hindi": ("Hindi", "hi"),
    "Bengali": ("Bengali", "bn"),
    "Tamil": ("Tamil", "ta"),
    "Telugu": ("Telugu", "te"),
    "Marathi": ("Marathi", "mr"),
    "Gujarati": ("Gujarati", "gu"),
    "Kannada": ("Kannada", "kn"),
    "Malayalam": ("Malayalam", "ml"),
    "Punjabi": ("Punjabi", "pa"),
    "Urdu": ("Urdu", "ur"),
    "Nepali": ("Nepali", "ne"),
    "Sinhala": ("Sinhala", "si"),
    # European - Western
    "French": ("French", "fr"),
    "German": ("German", "de"),
    "Spanish": ("Spanish", "es"),
    "Portuguese": ("Portuguese", "pt"),
    "Italian": ("Italian", "it"),
    "Dutch": ("Dutch", "nl"),
    # European - Northern
    "Swedish": ("Swedish", "sv"),
    "Norwegian": ("Norwegian", "no"),
    "Danish": ("Danish", "da"),
    "Finnish": ("Finnish", "fi"),
    "Icelandic": ("Icelandic", "is"),
    # European - Eastern
    "Russian": ("Russian", "ru"),
    "Polish": ("Polish", "pl"),
    "Ukrainian": ("Ukrainian", "uk"),
    "Czech": ("Czech", "cs"),
    "Romanian": ("Romanian", "ro"),
    "Hungarian": ("Hungarian", "hu"),
    "Bulgarian": ("Bulgarian", "bg"),
    "Slovak": ("Slovak", "sk"),
    "Croatian": ("Croatian", "hr"),
    "Serbian": ("Serbian", "sr"),
    "Slovenian": ("Slovenian", "sl"),
    "Lithuanian": ("Lithuanian", "lt"),
    "Latvian": ("Latvian", "lv"),
    "Estonian": ("Estonian", "et"),
    # European - Southern
    "Greek": ("Greek", "el"),
    "Turkish": ("Turkish", "tr"),
    # Middle Eastern
    "Arabic": ("Arabic", "ar"),
    "Hebrew": ("Hebrew", "he"),
    "Persian": ("Persian", "fa"),
    # African
    "Swahili": ("Swahili", "sw"),
    "Amharic": ("Amharic", "am"),
    "Hausa": ("Hausa", "ha"),
    "Yoruba": ("Yoruba", "yo"),
    "Zulu": ("Zulu", "zu"),
}

DATA_DIR = Path(os.environ.get("TRANSLATE_TOOL_DATA_DIR", Path.home() / ".translate_tool"))
JOBS_DIR = DATA_DIR / "jobs"
LOG_DIR = DATA_DIR / "logs"
TRANSLATION_CACHE_ENABLED = os.environ.get("TRANSLATION_CACHE_ENABLED", "1").lower() in ("1", "true", "yes")
CACHE_DIR = DATA_DIR / "cache"

DEFAULT_HOST = os.environ.get("TRANSLATE_TOOL_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.environ.get("TRANSLATE_TOOL_PORT", "8765"))

ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


@dataclass
class TimeoutConfig:
    """Configurable timeout values with env overrides."""

    _connect_timeout: Optional[float] = None
    _read_timeout: Optional[float] = None
    _config_connect: Optional[float] = None
    _config_read: Optional[float] = None

    def set_from_config(self, connect: Optional[float], read: Optional[float]) -> None:
        self._config_connect = connect
        self._config_read = read

    def set_timeouts(self, connect: Optional[float] = None, read: Optional[float] = None) -> None:
        self._connect_timeout = connect
        self._read_timeout = read

    def clear_runtime_overrides(self) -> None:
        self._connect_timeout = None
        self._read_timeout = None

    @property
    def connect_timeout(self) -> float:
        if self._connect_timeout is not None:
            return self._connect_timeout
        env_val = os.environ.get(ENV_CONNECT_TIMEOUT)
        if env_val:
            try:
                val = float(env_val)
                if val > 0:
                    return val
            except ValueError:
                pass
        if self._config_connect is not None:
            return self._config_connect
        return DEFAULT_CONNECT_TIMEOUT_S

    @property
    def read_timeout(self) -> float:
        if self._read_timeout is not None:
            return self._read_timeout
        env_val = os.environ.get(ENV_READ_TIMEOUT)
        if env_val:
            try:
                val = float(env_val)
                if val > 0:
                    return val
            except ValueError:
                pass
        if self._config_read is not None:
            return self._config_read
        return DEFAULT_READ_TIMEOUT_S

    def get_timeout_tuple(self) -> Tuple[float, float]:
        return (self.connect_timeout, self.read_timeout)


# ---------------------------------------------------------------------------
# Provider config loader (p1-cloud-providers)
# ---------------------------------------------------------------------------

# Default location for the providers registry relative to the repo root.
# Tests can override via the `config_path` argument.
_DEFAULT_PROVIDERS_YML = Path(__file__).parent.parent.parent / "config" / "providers.yml"

_ENV_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-(.*?))?\}")


def _expand_env_vars(value: str) -> Tuple[str, bool]:
    """Expand ``${VAR}`` and ``${VAR:-default}`` in *value*.

    Returns:
        (expanded_value, all_resolved) — all_resolved is False when at least one
        required ``${VAR}`` (no default) was unset in the environment.
    """
    all_resolved = True

    def _replace(m: "re.Match[str]") -> str:
        nonlocal all_resolved
        var_name = m.group(1)
        default = m.group(2)  # None when no ``:-default``
        env_val = os.environ.get(var_name)
        if env_val is not None:
            return env_val
        if default is not None:
            return default
        # Required var is unset → mark as unresolved, return empty string
        _cfg_logger.warning(
            "[providers] Required env var ${%s} is unset — provider will be disabled.",
            var_name,
        )
        all_resolved = False
        return ""

    expanded = _ENV_VAR_RE.sub(_replace, value)
    return expanded, all_resolved


def _expand_node(node: Any) -> Tuple[Any, bool]:
    """Recursively expand env vars in a parsed YAML node.

    Returns:
        (expanded_node, all_resolved)
    """
    if isinstance(node, str):
        return _expand_env_vars(node)
    if isinstance(node, dict):
        result: Dict[str, Any] = {}
        all_ok = True
        for k, v in node.items():
            expanded_v, ok = _expand_node(v)
            result[k] = expanded_v
            if not ok:
                all_ok = False
        return result, all_ok
    if isinstance(node, list):
        result_list: List[Any] = []
        all_ok = True
        for item in node:
            expanded_item, ok = _expand_node(item)
            result_list.append(expanded_item)
            if not ok:
                all_ok = False
        return result_list, all_ok
    # bool / int / float / None — pass through unchanged
    return node, True


def load_providers_config(
    config_path: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    """Load and parse ``providers.yml``, expanding ``${VAR:-default}`` env vars.

    Behavior per BR-13, BR-17:
    - File absent / unreadable / malformed → return None (caller falls back to Ollama).
    - Provider whose required env var is unresolved → that provider's ``enabled``
      is forced to False (not removed; BR-17).
    - All providers disabled (after resolution) → return config with the
      ``_all_disabled`` sentinel so callers can fall back to Ollama (BR-13).

    Args:
        config_path: Override path for testing; defaults to ``config/providers.yml``.

    Returns:
        Parsed + interpolated config dict, or None on load failure.
    """
    try:
        import yaml  # PyYAML is a project dependency
    except ImportError:
        _cfg_logger.error("[providers] PyYAML not installed; cannot load providers.yml")
        return None

    path = Path(config_path) if config_path is not None else _DEFAULT_PROVIDERS_YML

    if not path.exists():
        _cfg_logger.info("[providers] providers.yml not found at %s — using Ollama fallback", path)
        return None

    try:
        raw_text = path.read_text(encoding="utf-8")
        raw_config = yaml.safe_load(raw_text)
    except Exception as exc:
        _cfg_logger.warning("[providers] Failed to load providers.yml: %s — using Ollama fallback", exc)
        return None

    if not isinstance(raw_config, dict):
        _cfg_logger.warning("[providers] providers.yml is not a mapping — using Ollama fallback")
        return None

    # Expand env vars recursively; track per-provider resolution failures.
    providers_raw: List[Dict[str, Any]] = raw_config.get("providers", [])
    expanded_providers: List[Dict[str, Any]] = []
    for provider in providers_raw:
        expanded_provider, all_resolved = _expand_node(provider)
        if not all_resolved:
            # BR-17: unresolved required var → disable the provider
            _cfg_logger.warning(
                "[providers] Provider '%s' has unresolved env vars — disabling.",
                provider.get("id", "<unknown>"),
            )
            expanded_provider["enabled"] = False
        else:
            # Expand the enabled field independently (it may be a bool string like "false")
            enabled_raw = expanded_provider.get("enabled", True)
            if isinstance(enabled_raw, str):
                expanded_provider["enabled"] = enabled_raw.lower() not in ("false", "0", "no")
        expanded_providers.append(expanded_provider)

    # Expand the rest of the config (routing, fallback_chain, etc.)
    rest = {k: v for k, v in raw_config.items() if k != "providers"}
    expanded_rest, _ = _expand_node(rest)

    config: Dict[str, Any] = {**expanded_rest, "providers": expanded_providers}

    return config
