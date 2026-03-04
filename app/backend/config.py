"""
Backend configuration for Translate Tool.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, Optional, Tuple


class ModelType(str, Enum):
    """Supported translation model categories."""

    GENERAL = "general"
    TRANSLATION = "translation"

APP_NAME = "Translate Tool"
DEFAULT_MODEL = "qwen3.5:4b"
HYMT_DEFAULT_MODEL = os.environ.get("HYMT_DEFAULT_MODEL", "demonbyron/HY-MT1.5-7B:Q4_K_M")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_NUM_GPU = int(os.environ.get("OLLAMA_NUM_GPU", "99"))
OLLAMA_KV_CACHE_TYPE = os.environ.get("OLLAMA_KV_CACHE_TYPE", "q8_0")

# OLLAMA_NUM_CTX env override applies to all model types for backward compatibility.
_NUM_CTX_OVERRIDE = os.environ.get("OLLAMA_NUM_CTX")
GENERAL_NUM_CTX = int(_NUM_CTX_OVERRIDE) if _NUM_CTX_OVERRIDE else 4096
TRANSLATION_NUM_CTX = int(_NUM_CTX_OVERRIDE) if _NUM_CTX_OVERRIDE else 3072

# Keep legacy constant name for downstream modules.
OLLAMA_NUM_CTX = GENERAL_NUM_CTX

MODEL_TYPE_OPTIONS: Dict[ModelType, Dict[str, object]] = {
    ModelType.GENERAL: {
        "num_ctx": GENERAL_NUM_CTX,
        "num_gpu": OLLAMA_NUM_GPU,
        "kv_cache_type": OLLAMA_KV_CACHE_TYPE,
        "frequency_penalty": 0.5,  # Penalise repetitive loops without hurting terminology consistency.
    },
    ModelType.TRANSLATION: {
        "num_ctx": TRANSLATION_NUM_CTX,
        "num_gpu": OLLAMA_NUM_GPU,
        "kv_cache_type": OLLAMA_KV_CACHE_TYPE,
        "top_k": 20,
        "top_p": 0.6,
        "repeat_penalty": 1.05,
        "temperature": 0.7,
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
# Merge multiple paragraphs for context-aware translation (within MAX_PARAGRAPH_CHARS)
USE_MERGED_CONTEXT = True
EXCEL_FORMULA_MODE = "skip"
MAX_SHAPE_CHARS = 1200

# PDF parsing configuration
PDF_PARSER_ENGINE = "pymupdf"  # pymupdf | pypdf2 (fallback)
PDF_SKIP_HEADER_FOOTER = False  # Skip header/footer translation
PDF_HEADER_FOOTER_MARGIN_PT = 50  # Margin for header/footer detection (points)

# Layout preservation configuration
LAYOUT_PRESERVATION_MODE = "inline"  # inline | overlay | side_by_side
DEFAULT_FONT_FAMILY = "NotoSansSC"  # Default font for PDF rendering
MIN_FONT_SIZE_PT = 6  # Minimum font size for scaling
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

SUPPORTED_EXTENSIONS = {".docx", ".doc", ".pptx", ".xlsx", ".xls", ".pdf"}

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
