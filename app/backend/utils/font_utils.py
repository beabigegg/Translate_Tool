"""Font utilities for PDF rendering.

This module provides font registration, language-to-font mapping,
text width calculation, and text fitting for bounding boxes.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from reportlab.lib.fonts import addMapping
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from app.backend.config import (
    DEFAULT_FONT_FAMILY,
    FONT_SIZE_SHRINK_FACTOR,
    LANG_CODE_MAP,
    MAX_FONT_SIZE_PT,
    MIN_FONT_SIZE_PT,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Expansion-factor table (BR-37, AC-8)
# Advisory language-pair expansion coefficients used to pre-size the initial
# fit attempt.  The measured rendered width always governs the actual decision;
# these factors are never hard-coded in the renderer.
# ---------------------------------------------------------------------------

#: Per-language-pair expansion coefficients (source_lang, target_lang) → factor.
#: Only covers the documented benchmark pairs (en→de/es/fr).
EXPANSION_FACTOR_TABLE: Dict[Tuple[str, str], float] = {
    ("en", "de"): 1.30,
    ("en", "es"): 1.25,
    ("en", "fr"): 1.20,
}

#: Default advisory factor for any language pair not in the table (BR-37).
DEFAULT_EXPANSION_FACTOR: float = 1.15


def get_expansion_factor(src_lang: str, tgt_lang: str) -> float:
    """Return the advisory expansion factor for a source→target language pair.

    Args:
        src_lang: ISO source language code (e.g. "en").
        tgt_lang: ISO target language code (e.g. "de").

    Returns:
        Expansion factor from EXPANSION_FACTOR_TABLE, or DEFAULT_EXPANSION_FACTOR
        when the pair is not listed.  This value is advisory only — the measured
        rendered width always governs the actual fit decision (BR-37).
    """
    return EXPANSION_FACTOR_TABLE.get((src_lang, tgt_lang), DEFAULT_EXPANSION_FACTOR)


# ---------------------------------------------------------------------------
# Per-face metrics memoization (BR-39)
# Metrics are read once per registered face and stored here.  This avoids
# repeated font-file I/O when the fallback chain compares multiple candidates.
# ---------------------------------------------------------------------------
_face_metrics_cache: Dict[str, Dict[str, float]] = {}


def _get_face_metrics(font_name: str) -> Dict[str, float]:
    """Return x-height, cap-height, and mean advance-width for a registered face.

    Metrics are memoized per face name.  Falls back to zero-dict on any error
    so the fallback chain can still operate (Noto terminal fallback catches edge cases).

    Args:
        font_name: A font name registered with ReportLab pdfmetrics.

    Returns:
        Dict with keys ``x_height``, ``cap_height``, ``advance_width``.
    """
    if font_name in _face_metrics_cache:
        return _face_metrics_cache[font_name]

    metrics: Dict[str, float] = {"x_height": 0.0, "cap_height": 0.0, "advance_width": 0.0}

    try:
        font = pdfmetrics.getFont(font_name)
        # ReportLab TTFont exposes face.ascent / descent via the underlying TTFont object
        face = getattr(font, "face", None)
        if face is not None:
            # x-height: typically encoded as OS/2 sxHeight (in font units, 1000 upem assumed)
            x_height = getattr(face, "xHeight", None)
            cap_height = getattr(face, "capHeight", None)
            # Advance width proxy: use width of 'x' at 1000pt
            try:
                adv = font.stringWidth("x", 1000)
            except Exception:
                adv = 0.0

            metrics["x_height"] = float(x_height) if x_height else 0.0
            metrics["cap_height"] = float(cap_height) if cap_height else 0.0
            metrics["advance_width"] = float(adv)
    except Exception:
        pass  # Return zero-dict; terminal Noto fallback handles the edge case

    _face_metrics_cache[font_name] = metrics
    return metrics


def get_metric_compatible_fallback(
    primary_face: str,
    target_char: str,
    registered_faces: List[str],
) -> str:
    """Select the metric-compatible fallback font for a character (BR-39, AC-3/AC-7).

    When ``get_font_for_language`` resolves a font that lacks a glyph for
    ``target_char``, this function selects a replacement face from
    ``registered_faces`` by comparing x-height (primary), cap-height
    (secondary), and mean advance-width (tertiary) against ``primary_face``
    metrics.

    Selection is restricted to already-registered faces so no new font I/O
    occurs beyond the initial load cached by ``_load_font_buffer``.  Metrics
    are memoized per face (``_face_metrics_cache``).

    The Noto terminal fallback rule (BR-39):
    - If no registered face provides a match, fall back to ``NotoSans``.
    - If ``NotoSans`` is not registered, fall back to ``Helvetica`` (built-in).

    Args:
        primary_face: The originally-selected font name whose metrics are the target.
        target_char: The character that may be missing from ``primary_face``.
        registered_faces: Candidate font names (already registered with pdfmetrics).

    Returns:
        The best-matching registered font name (never raises; always returns a string).
    """
    if not registered_faces:
        return "Helvetica"

    primary_metrics = _get_face_metrics(primary_face)

    best_face: Optional[str] = None
    best_distance: float = float("inf")

    for face in registered_faces:
        if face == primary_face:
            # Skip primary itself; we're looking for a fallback
            continue
        m = _get_face_metrics(face)
        # Weighted distance: x-height (3×), cap-height (2×), advance-width (1×)
        dist = (
            3.0 * abs(m["x_height"] - primary_metrics["x_height"])
            + 2.0 * abs(m["cap_height"] - primary_metrics["cap_height"])
            + 1.0 * abs(m["advance_width"] - primary_metrics["advance_width"])
        )
        if dist < best_distance:
            best_distance = dist
            best_face = face

    if best_face is not None:
        return best_face

    # Noto terminal fallback (BR-39)
    for noto_name in ("NotoSans", "NotoSansSC", "NotoSansTC"):
        try:
            pdfmetrics.getFont(noto_name)
            return noto_name
        except KeyError:
            continue

    # Last resort: Helvetica (always available in ReportLab)
    return "Helvetica"

# Font registration status
_fonts_registered = False

# System font paths to search (project local fonts first for priority)
SYSTEM_FONT_PATHS = [
    # Project local fonts (highest priority)
    Path(__file__).parent.parent / "fonts",
    # Linux
    Path("/usr/share/fonts/opentype/noto"),
    Path("/usr/share/fonts/truetype/noto"),
    Path("/usr/share/fonts/google-noto"),
    # macOS
    Path("/Library/Fonts"),
    Path.home() / "Library/Fonts",
    # Windows
    Path("C:/Windows/Fonts"),
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
        "NotoSansJP-Variable.ttf",  # Variable TTF (works with ReportLab)
        "NotoSansJP-Regular.ttf",
        "NotoSansJP-Regular.otf",  # OpenType CFF (PyMuPDF only)
        "NotoSansJP[wght].ttf",
        "NotoSansCJK-Regular.ttc",
    ]),
    "ko": ("NotoSansKR", [
        "NotoSansKR-Variable.ttf",  # Variable TTF (works with ReportLab)
        "NotoSansKR-Regular.ttf",
        "NotoSansKR-Regular.otf",  # OpenType CFF (PyMuPDF only)
        "NotoSansKR[wght].ttf",
        "NotoSansCJK-Regular.ttc",
    ]),
    # Thai
    "th": ("NotoSansThai", ["NotoSansThai-Regular.ttf"]),
    # Arabic (RTL)
    "ar": ("NotoSansArabic", ["NotoSansArabic-Regular.ttf"]),
    # Hebrew (RTL)
    "he": ("NotoSansHebrew", ["NotoSansHebrew-Regular.ttf"]),
    # Vietnamese (Latin with diacritics)
    "vi": ("NotoSans", ["NotoSans-Regular.ttf", "NotoSans[wght].ttf", "DejaVuSans.ttf"]),
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
            # For CJK languages that failed (e.g., OTF with CFF outlines),
            # register an alias to Traditional Chinese font as fallback
            if lang_code in ("ja", "ko"):
                try:
                    # Check if NotoSansTC is registered, use it as fallback
                    pdfmetrics.getFont("NotoSansTC")
                    # Create an alias
                    pdfmetrics.registerFontFamily(
                        font_name,
                        normal="NotoSansTC",
                    )
                    logger.info(
                        f"Using NotoSansTC as fallback for {lang_code} ({font_name})"
                    )
                except KeyError:
                    logger.warning(
                        f"Font not found or failed for {lang_code}: {patterns}"
                    )
            else:
                logger.warning(
                    f"Font not found or failed for {lang_code}: {patterns}"
                )

    _fonts_registered = True
    logger.info(f"Registered {registered_count} fonts for PDF rendering")
    return registered_count > 0


def _normalize_lang_code(lang: str) -> str:
    """Convert language name or code to normalized code.

    Args:
        lang: Language name (e.g., "Traditional Chinese") or code (e.g., "zh-TW").

    Returns:
        Normalized ISO language code (e.g., "zh-TW").
    """
    # If already a code (contains hyphen or is short), return as-is
    if "-" in lang or len(lang) <= 3:
        return lang

    # Look up in LANG_CODE_MAP (language name -> code)
    if lang in LANG_CODE_MAP:
        return LANG_CODE_MAP[lang][1]

    # Case-insensitive lookup
    lang_lower = lang.lower()
    for name, (_, code) in LANG_CODE_MAP.items():
        if name.lower() == lang_lower:
            return code

    # Fallback: return as-is
    return lang


def get_font_for_language(lang: str) -> str:
    """Get the appropriate font name for a language.

    Args:
        lang: Language name (e.g., 'Traditional Chinese') or code (e.g., 'zh-TW').

    Returns:
        Font name to use for the language.
    """
    # Ensure fonts are registered
    register_fonts()

    # Convert language name to code if needed
    lang_code = _normalize_lang_code(lang)

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

    # CJK fallback: use Traditional Chinese font for Japanese/Korean
    # (shares many glyphs, better than Helvetica for CJK text)
    if lang_code in ("ja", "ko") or lang_family in ("ja", "ko"):
        try:
            pdfmetrics.getFont("NotoSansTC")
            logger.debug(f"Using NotoSansTC as CJK fallback for {lang_code}")
            return "NotoSansTC"
        except KeyError:
            pass

    # Fallback to default
    return LANGUAGE_FONT_MAP["default"][0]


def _is_cjk_char(ch: str) -> bool:
    """Return True for full-width CJK characters (rendered at ~1 em advance)."""
    code = ord(ch)
    return (
        0x4E00 <= code <= 0x9FFF      # CJK Unified Ideographs
        or 0x3400 <= code <= 0x4DBF   # CJK Extension A
        or 0x3000 <= code <= 0x303F   # CJK punctuation
        or 0x3040 <= code <= 0x30FF   # Hiragana / Katakana
        or 0xAC00 <= code <= 0xD7AF   # Hangul syllables
        or 0xF900 <= code <= 0xFAFF   # CJK Compatibility Ideographs
        or 0xFF00 <= code <= 0xFF60   # Full-width forms
    )


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
    except KeyError:
        # Fallback to Helvetica
        font = pdfmetrics.getFont("Helvetica")

    # Built-in Type1 fonts (Helvetica etc.) carry no CJK glyphs and under-measure
    # full-width characters.  Estimate each CJK char at 1 em so fit decisions made
    # against a missing/unregistered font never under-count the rendered width.
    if not isinstance(font, TTFont) and any(_is_cjk_char(ch) for ch in text):
        non_cjk = "".join(ch for ch in text if not _is_cjk_char(ch))
        cjk_count = len(text) - len(non_cjk)
        return font.stringWidth(non_cjk, font_size) + cjk_count * font_size

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


# Required fonts for full language support
REQUIRED_FONTS = {
    "zh-TW": {
        "name": "Traditional Chinese",
        "patterns": ["NotoSansTC-Regular.ttf", "NotoSansTC[wght].ttf"],
        "download_url": "https://fonts.google.com/noto/specimen/Noto+Sans+TC",
    },
    "zh-CN": {
        "name": "Simplified Chinese",
        "patterns": ["NotoSansSC-Regular.ttf", "NotoSansSC[wght].ttf"],
        "download_url": "https://fonts.google.com/noto/specimen/Noto+Sans+SC",
    },
    "ja": {
        "name": "Japanese",
        "patterns": ["NotoSansJP-Variable.ttf", "NotoSansJP-Regular.ttf", "NotoSansJP-Regular.otf"],
        "download_url": "https://fonts.google.com/noto/specimen/Noto+Sans+JP",
    },
    "ko": {
        "name": "Korean",
        "patterns": ["NotoSansKR-Variable.ttf", "NotoSansKR-Regular.ttf", "NotoSansKR-Regular.otf"],
        "download_url": "https://fonts.google.com/noto/specimen/Noto+Sans+KR",
    },
    "th": {
        "name": "Thai",
        "patterns": ["NotoSansThai-Regular.ttf"],
        "download_url": "https://fonts.google.com/noto/specimen/Noto+Sans+Thai",
    },
    "ar": {
        "name": "Arabic",
        "patterns": ["NotoSansArabic-Regular.ttf"],
        "download_url": "https://fonts.google.com/noto/specimen/Noto+Sans+Arabic",
    },
    "he": {
        "name": "Hebrew",
        "patterns": ["NotoSansHebrew-Regular.ttf"],
        "download_url": "https://fonts.google.com/noto/specimen/Noto+Sans+Hebrew",
    },
    "vi": {
        "name": "Vietnamese",
        "patterns": ["NotoSans-Regular.ttf", "NotoSans[wght].ttf", "DejaVuSans.ttf"],
        "download_url": "https://fonts.google.com/noto/specimen/Noto+Sans",
    },
}


def check_required_fonts(languages: Optional[List[str]] = None) -> dict:
    """Check if required fonts are available for specified languages.

    Args:
        languages: List of language codes to check. If None, checks all CJK languages.

    Returns:
        Dict with 'available' and 'missing' lists of language info.
    """
    if languages is None:
        # Default to checking CJK languages
        languages = ["zh-TW", "zh-CN", "ja", "ko"]

    available = []
    missing = []

    for lang_code in languages:
        lang_lower = lang_code.lower()

        # Find the font info
        font_info = REQUIRED_FONTS.get(lang_lower)
        if font_info is None:
            # Try to find by full code
            for key, info in REQUIRED_FONTS.items():
                if key == lang_lower:
                    font_info = info
                    break

        if font_info is None:
            continue  # Not a font-requiring language

        # Check if font exists
        font_path = find_font_file(font_info["patterns"])
        if font_path:
            available.append({
                "code": lang_code,
                "name": font_info["name"],
                "path": str(font_path),
            })
        else:
            missing.append({
                "code": lang_code,
                "name": font_info["name"],
                "patterns": font_info["patterns"],
                "download_url": font_info["download_url"],
            })

    return {"available": available, "missing": missing}


def get_font_check_message(languages: Optional[list[str]] = None) -> Optional[str]:
    """Get a user-friendly message about missing fonts.

    Args:
        languages: List of language codes to check.

    Returns:
        Warning message if fonts are missing, None if all fonts are available.
    """
    result = check_required_fonts(languages)
    if not result["missing"]:
        return None

    lines = ["⚠️ 缺少部分語言的字型檔案，PDF 輸出可能無法正確顯示："]
    lines.append("")

    for font in result["missing"]:
        lines.append(f"  • {font['name']} ({font['code']})")
        lines.append(f"    下載: {font['download_url']}")

    lines.append("")
    lines.append("請將字型檔案放置於以下任一位置：")
    lines.append(f"  • {Path(__file__).parent.parent / 'fonts'}")
    lines.append("  • 系統字型資料夾")

    return "\n".join(lines)
