"""
Backend configuration for Translate Tool.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

APP_NAME = "Translate Tool"
DEFAULT_MODEL = "translategemma:12b"
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

DEFAULT_CONNECT_TIMEOUT_S = 10.0
DEFAULT_READ_TIMEOUT_S = 180.0

API_ATTEMPTS = 3
API_BACKOFF_BASE = 1.6
SENTENCE_MODE = True
INSERT_FONT_SIZE_PT = 10

DEFAULT_BATCH_SIZE = 10
MIN_BATCH_SIZE = 1
MAX_BATCH_SIZE = 50
BATCH_SEPARATOR = "\n---SEGMENT_SEPARATOR---\n"

# Character-based batching (optimized for 128K context window)
DEFAULT_MAX_BATCH_CHARS = 80000   # ~80K chars per batch
MIN_MAX_BATCH_CHARS = 10000       # Minimum 10K chars
MAX_MAX_BATCH_CHARS = 100000      # Maximum 100K chars

# Translation granularity: "sentence" (legacy) | "paragraph" (recommended for quality)
TRANSLATION_GRANULARITY = "paragraph"
MAX_PARAGRAPH_CHARS = 2000  # Split paragraphs longer than this
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

MAX_SEGMENTS = 10000
MAX_TEXT_LENGTH = 100000

# Performance: Job management
MAX_JOBS_IN_MEMORY = int(os.environ.get("MAX_JOBS_IN_MEMORY", "100"))
JOB_TTL_HOURS = int(os.environ.get("JOB_TTL_HOURS", "24"))
CLEANUP_INTERVAL_MINUTES = int(os.environ.get("CLEANUP_INTERVAL_MINUTES", "30"))

# Performance: Cache management
CACHE_MAX_ENTRIES = int(os.environ.get("CACHE_MAX_ENTRIES", "50000"))
CACHE_CLEANUP_BATCH = int(os.environ.get("CACHE_CLEANUP_BATCH", "5000"))

# Performance: SSE stream management
SSE_IDLE_TIMEOUT_SECONDS = int(os.environ.get("SSE_IDLE_TIMEOUT_SECONDS", "60"))

# Performance: HTTP connection pool
HTTP_POOL_CONNECTIONS = int(os.environ.get("HTTP_POOL_CONNECTIONS", "2"))
HTTP_POOL_MAXSIZE = int(os.environ.get("HTTP_POOL_MAXSIZE", "5"))

ENV_CONNECT_TIMEOUT = "TRANSLATE_CONNECT_TIMEOUT"
ENV_READ_TIMEOUT = "TRANSLATE_READ_TIMEOUT"

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
