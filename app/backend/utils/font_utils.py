"""Font utilities for PDF rendering.

This module provides font registration, language-to-font mapping,
text width calculation, and text fitting for bounding boxes.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Tuple

from reportlab.lib.fonts import addMapping
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from app.backend.config import (
    DEFAULT_FONT_FAMILY,
    FONT_SIZE_SHRINK_FACTOR,
    MAX_FONT_SIZE_PT,
    MIN_FONT_SIZE_PT,
)

logger = logging.getLogger(__name__)

# Font registration status
_fonts_registered = False

# System font paths to search
SYSTEM_FONT_PATHS = [
    # Linux
    Path("/usr/share/fonts/opentype/noto"),
    Path("/usr/share/fonts/truetype/noto"),
    Path("/usr/share/fonts/google-noto"),
    # macOS
    Path("/Library/Fonts"),
    Path.home() / "Library/Fonts",
    # Windows
    Path("C:/Windows/Fonts"),
    # Project local fonts
    Path(__file__).parent.parent / "fonts",
]

# Font mapping: language code -> (font name, font file patterns)
# Priority order: project local fonts (TTF) > system TTC fonts
LANGUAGE_FONT_MAP = {
    # CJK languages - prefer individual TTF fonts from project fonts dir
    "zh-TW": ("NotoSansTC", [
        "NotoSansTC-Regular.ttf",  # Project local font
        "NotoSansTC[wght].ttf",    # Variable font
        "NotoSansCJK-Regular.ttc",  # System TTC (may not work)
    ]),
    "zh-CN": ("NotoSansSC", [
        "NotoSansSC-Regular.ttf",
        "NotoSansSC[wght].ttf",
        "NotoSansCJK-Regular.ttc",
    ]),
    "ja": ("NotoSansJP", [
        "NotoSansJP-Regular.ttf",
        "NotoSansJP[wght].ttf",
        "NotoSansCJK-Regular.ttc",
    ]),
    "ko": ("NotoSansKR", [
        "NotoSansKR-Regular.ttf",
        "NotoSansKR[wght].ttf",
        "NotoSansCJK-Regular.ttc",
    ]),
    # Thai
    "th": ("NotoSansThai", ["NotoSansThai-Regular.ttf"]),
    # Arabic (RTL)
    "ar": ("NotoSansArabic", ["NotoSansArabic-Regular.ttf"]),
    # Hebrew (RTL)
    "he": ("NotoSansHebrew", ["NotoSansHebrew-Regular.ttf"]),
    # Default/Latin
    "default": ("Helvetica", []),  # Built-in, no file needed
}

# CJK font index in TTC files (NotoSansCJK-Regular.ttc)
CJK_TTC_INDICES = {
    "NotoSansCJK-SC": 2,  # Simplified Chinese
    "NotoSansCJK-TC": 3,  # Traditional Chinese
    "NotoSansCJK-JP": 0,  # Japanese
    "NotoSansCJK-KR": 1,  # Korean
    "NotoSansCJK-HK": 4,  # Hong Kong
}


def find_font_file(patterns: list[str]) -> Optional[Path]:
    """Find a font file matching the given patterns.

    Args:
        patterns: List of font file name patterns to search for.

    Returns:
        Path to the font file if found, None otherwise.
    """
    for base_path in SYSTEM_FONT_PATHS:
        if not base_path.exists():
            continue
        for pattern in patterns:
            # Direct match
            font_path = base_path / pattern
            if font_path.exists():
                return font_path
            # Glob search
            matches = list(base_path.glob(f"**/{pattern}"))
            if matches:
                return matches[0]
    return None


def register_fonts() -> bool:
    """Register fonts for PDF generation.

    This function registers CJK and other language-specific fonts
    with ReportLab's font system.

    Returns:
        True if fonts were registered successfully.
    """
    global _fonts_registered
    if _fonts_registered:
        return True

    registered_count = 0

    for lang_code, (font_name, patterns) in LANGUAGE_FONT_MAP.items():
        if font_name == "Helvetica":
            # Built-in font, no registration needed
            continue

        # Try each pattern until one works
        registered = False
        for pattern in patterns:
            font_path = find_font_file([pattern])
            if font_path is None:
                continue

            try:
                if font_path.suffix.lower() == ".ttc":
                    # TrueType Collection - need to specify font index
                    # Note: TTC with CFF outlines may not work with reportlab
                    ttc_index = CJK_TTC_INDICES.get(font_name, 0)
                    font = TTFont(font_name, str(font_path), subfontIndex=ttc_index)
                else:
                    font = TTFont(font_name, str(font_path))

                pdfmetrics.registerFont(font)
                addMapping(font_name, 0, 0, font_name)  # normal
                registered_count += 1
                registered = True
                logger.debug(f"Registered font: {font_name} from {font_path}")
                break  # Successfully registered, stop trying patterns
            except Exception as exc:
                logger.debug(f"Failed to register font {font_name} from {font_path}: {exc}")
                continue

        if not registered:
            logger.warning(f"Font not found or failed for {lang_code}: {patterns}")

    _fonts_registered = True
    logger.info(f"Registered {registered_count} fonts for PDF rendering")
    return registered_count > 0


def get_font_for_language(lang_code: str) -> str:
    """Get the appropriate font name for a language.

    Args:
        lang_code: ISO language code (e.g., 'zh-TW', 'ja', 'ko').

    Returns:
        Font name to use for the language.
    """
    # Ensure fonts are registered
    register_fonts()

    # Direct match
    if lang_code in LANGUAGE_FONT_MAP:
        font_name = LANGUAGE_FONT_MAP[lang_code][0]
        # Check if font is available
        try:
            pdfmetrics.getFont(font_name)
            return font_name
        except KeyError:
            pass

    # Language family match (e.g., 'zh' matches 'zh-TW')
    lang_family = lang_code.split("-")[0]
    for code, (font_name, _) in LANGUAGE_FONT_MAP.items():
        if code.startswith(lang_family):
            try:
                pdfmetrics.getFont(font_name)
                return font_name
            except KeyError:
                continue

    # Fallback to default
    return LANGUAGE_FONT_MAP["default"][0]


def calculate_text_width(text: str, font_name: str, font_size: float) -> float:
    """Calculate the width of text in points.

    Args:
        text: Text to measure.
        font_name: Font name to use.
        font_size: Font size in points.

    Returns:
        Width of the text in points.
    """
    try:
        font = pdfmetrics.getFont(font_name)
        return font.stringWidth(text, font_size)
    except KeyError:
        # Fallback to Helvetica
        font = pdfmetrics.getFont("Helvetica")
        return font.stringWidth(text, font_size)


def calculate_text_height(font_name: str, font_size: float) -> float:
    """Calculate the height of text in points.

    Args:
        font_name: Font name to use.
        font_size: Font size in points.

    Returns:
        Height of the text in points (approximation based on font size).
    """
    # Standard line height is approximately 1.2x font size
    return font_size * 1.2


def estimate_font_size_from_bbox(
    bbox_height: float,
    line_count: int = 1,
) -> float:
    """Estimate appropriate font size based on bounding box height.

    Args:
        bbox_height: Height of the bounding box in points.
        line_count: Number of text lines.

    Returns:
        Estimated font size in points.
    """
    # Account for line spacing (1.2x) and leave some padding
    padding_factor = 0.85
    font_size = (bbox_height / line_count) * padding_factor / 1.2

    # Clamp to min/max
    return max(MIN_FONT_SIZE_PT, min(MAX_FONT_SIZE_PT, font_size))


def fit_text_to_bbox(
    text: str,
    bbox_width: float,
    bbox_height: float,
    font_name: str,
    initial_font_size: Optional[float] = None,
    min_font_size: float = MIN_FONT_SIZE_PT,
    shrink_factor: float = FONT_SIZE_SHRINK_FACTOR,
) -> Tuple[float, bool]:
    """Find the best font size to fit text within a bounding box.

    Args:
        text: Text to fit.
        bbox_width: Width of the bounding box in points.
        bbox_height: Height of the bounding box in points.
        font_name: Font name to use.
        initial_font_size: Starting font size (if None, estimated from bbox).
        min_font_size: Minimum allowed font size.
        shrink_factor: Factor to reduce font size by each iteration.

    Returns:
        Tuple of (final_font_size, fits_in_bbox).
    """
    # Estimate initial font size from height if not provided
    if initial_font_size is None:
        line_count = text.count("\n") + 1
        initial_font_size = estimate_font_size_from_bbox(bbox_height, line_count)

    font_size = initial_font_size
    fits = False

    while font_size >= min_font_size:
        # Calculate text dimensions
        lines = text.split("\n")
        max_line_width = max(calculate_text_width(line, font_name, font_size) for line in lines)
        total_height = calculate_text_height(font_name, font_size) * len(lines)

        # Check if it fits
        if max_line_width <= bbox_width and total_height <= bbox_height:
            fits = True
            break

        # Shrink and try again
        font_size *= shrink_factor

    # Ensure we don't go below minimum
    font_size = max(font_size, min_font_size)

    if not fits:
        logger.warning(
            f"Text does not fit in bbox even at minimum font size {min_font_size}pt: "
            f"text='{text[:30]}...', bbox=({bbox_width:.1f}, {bbox_height:.1f})"
        )

    return font_size, fits


def detect_text_direction(text: str) -> str:
    """Detect text direction (LTR or RTL).

    Args:
        text: Text to analyze.

    Returns:
        'rtl' for right-to-left text, 'ltr' for left-to-right.
    """
    # RTL Unicode ranges: Arabic, Hebrew
    rtl_ranges = [
        (0x0590, 0x05FF),  # Hebrew
        (0x0600, 0x06FF),  # Arabic
        (0x0750, 0x077F),  # Arabic Supplement
        (0xFB50, 0xFDFF),  # Arabic Presentation Forms-A
        (0xFE70, 0xFEFF),  # Arabic Presentation Forms-B
    ]

    rtl_count = 0
    total_count = 0

    for char in text:
        code = ord(char)
        if char.isalpha():
            total_count += 1
            for start, end in rtl_ranges:
                if start <= code <= end:
                    rtl_count += 1
                    break

    # If more than 50% of alphabetic characters are RTL
    if total_count > 0 and rtl_count / total_count > 0.5:
        return "rtl"
    return "ltr"
