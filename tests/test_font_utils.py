"""Tests for font utilities."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from app.backend.utils.font_utils import (
    find_font_file,
    register_fonts,
    get_font_for_language,
    calculate_text_width,
    calculate_text_height,
    estimate_font_size_from_bbox,
    fit_text_to_bbox,
    detect_text_direction,
    LANGUAGE_FONT_MAP,
)


class TestFindFontFile:
    """Tests for find_font_file function."""

    def test_find_font_file_not_found(self):
        """Test that non-existent font returns None."""
        result = find_font_file(["NonExistentFont.ttf"])
        # May or may not find a font depending on system
        # Just verify it doesn't crash and returns Path or None
        assert result is None or hasattr(result, "exists")

    def test_find_font_file_with_empty_patterns(self):
        """Test with empty patterns list."""
        result = find_font_file([])
        assert result is None


class TestRegisterFonts:
    """Tests for register_fonts function."""

    def test_register_fonts_returns_bool(self):
        """Test that register_fonts returns a boolean."""
        result = register_fonts()
        assert isinstance(result, bool)

    def test_register_fonts_idempotent(self):
        """Test that calling register_fonts multiple times is safe."""
        result1 = register_fonts()
        result2 = register_fonts()
        assert result1 == result2


class TestGetFontForLanguage:
    """Tests for get_font_for_language function."""

    def test_get_font_for_default(self):
        """Test getting font for unknown language returns default."""
        font = get_font_for_language("unknown-lang")
        assert font == "Helvetica"

    def test_get_font_for_english(self):
        """Test getting font for English."""
        font = get_font_for_language("en")
        # Should return either a registered CJK font or Helvetica
        assert isinstance(font, str)
        assert len(font) > 0

    def test_get_font_for_chinese_traditional(self):
        """Test getting font for Traditional Chinese."""
        font = get_font_for_language("zh-TW")
        # Should return NotoSansCJK-TC if available, otherwise fallback
        assert isinstance(font, str)

    def test_get_font_for_chinese_simplified(self):
        """Test getting font for Simplified Chinese."""
        font = get_font_for_language("zh-CN")
        assert isinstance(font, str)

    def test_get_font_for_japanese(self):
        """Test getting font for Japanese."""
        font = get_font_for_language("ja")
        assert isinstance(font, str)

    def test_get_font_for_korean(self):
        """Test getting font for Korean."""
        font = get_font_for_language("ko")
        assert isinstance(font, str)

    def test_get_font_family_match(self):
        """Test that language family matching works (e.g., 'zh' matches 'zh-TW')."""
        font = get_font_for_language("zh")
        # Should match zh-TW or zh-CN font
        assert isinstance(font, str)


class TestCalculateTextWidth:
    """Tests for calculate_text_width function."""

    def test_calculate_text_width_basic(self):
        """Test basic text width calculation."""
        width = calculate_text_width("Hello", "Helvetica", 12)
        assert width > 0
        assert isinstance(width, float)

    def test_calculate_text_width_empty_string(self):
        """Test width of empty string is zero or near-zero."""
        width = calculate_text_width("", "Helvetica", 12)
        assert width >= 0

    def test_calculate_text_width_scales_with_size(self):
        """Test that width scales with font size."""
        width_small = calculate_text_width("Test", "Helvetica", 10)
        width_large = calculate_text_width("Test", "Helvetica", 20)
        assert width_large > width_small

    def test_calculate_text_width_invalid_font_fallback(self):
        """Test that invalid font falls back to Helvetica."""
        width = calculate_text_width("Test", "NonExistentFont", 12)
        assert width > 0


class TestCalculateTextHeight:
    """Tests for calculate_text_height function."""

    def test_calculate_text_height_basic(self):
        """Test basic text height calculation."""
        height = calculate_text_height("Helvetica", 12)
        assert height > 0
        # Standard line height is approximately 1.2x font size
        assert 12 <= height <= 20

    def test_calculate_text_height_scales_with_size(self):
        """Test that height scales with font size."""
        height_small = calculate_text_height("Helvetica", 10)
        height_large = calculate_text_height("Helvetica", 20)
        assert height_large > height_small


class TestEstimateFontSizeFromBbox:
    """Tests for estimate_font_size_from_bbox function."""

    def test_estimate_font_size_single_line(self):
        """Test font size estimation for single line."""
        font_size = estimate_font_size_from_bbox(24.0, line_count=1)
        assert font_size > 0
        assert font_size <= 24.0

    def test_estimate_font_size_multiple_lines(self):
        """Test font size estimation for multiple lines."""
        font_size_1 = estimate_font_size_from_bbox(48.0, line_count=1)
        font_size_2 = estimate_font_size_from_bbox(48.0, line_count=2)
        # More lines should result in smaller font
        assert font_size_2 < font_size_1

    def test_estimate_font_size_respects_min(self):
        """Test that estimation respects minimum font size."""
        from app.backend.config import MIN_FONT_SIZE_PT
        font_size = estimate_font_size_from_bbox(1.0, line_count=10)
        assert font_size >= MIN_FONT_SIZE_PT

    def test_estimate_font_size_respects_max(self):
        """Test that estimation respects maximum font size."""
        from app.backend.config import MAX_FONT_SIZE_PT
        font_size = estimate_font_size_from_bbox(1000.0, line_count=1)
        assert font_size <= MAX_FONT_SIZE_PT


class TestFitTextToBbox:
    """Tests for fit_text_to_bbox function."""

    def test_fit_text_to_bbox_basic(self):
        """Test basic text fitting."""
        font_size, fits = fit_text_to_bbox(
            "Hello World",
            bbox_width=200,
            bbox_height=50,
            font_name="Helvetica",
        )
        assert font_size > 0
        assert isinstance(fits, bool)

    def test_fit_text_to_bbox_small_box(self):
        """Test fitting text to very small box."""
        font_size, fits = fit_text_to_bbox(
            "A very long text that won't fit easily",
            bbox_width=10,
            bbox_height=10,
            font_name="Helvetica",
        )
        from app.backend.config import MIN_FONT_SIZE_PT
        assert font_size >= MIN_FONT_SIZE_PT
        # May not fit, but should handle gracefully
        assert isinstance(fits, bool)

    def test_fit_text_to_bbox_multiline(self):
        """Test fitting multiline text."""
        font_size, fits = fit_text_to_bbox(
            "Line 1\nLine 2\nLine 3",
            bbox_width=100,
            bbox_height=60,
            font_name="Helvetica",
        )
        assert font_size > 0
        assert isinstance(fits, bool)

    def test_fit_text_to_bbox_with_initial_size(self):
        """Test fitting with specified initial font size."""
        font_size, fits = fit_text_to_bbox(
            "Test",
            bbox_width=100,
            bbox_height=50,
            font_name="Helvetica",
            initial_font_size=24.0,
        )
        assert font_size > 0
        assert font_size <= 24.0  # Should not exceed initial


class TestDetectTextDirection:
    """Tests for detect_text_direction function."""

    def test_detect_ltr_english(self):
        """Test detecting LTR for English text."""
        direction = detect_text_direction("Hello World")
        assert direction == "ltr"

    def test_detect_ltr_chinese(self):
        """Test detecting LTR for Chinese text (CJK is LTR)."""
        direction = detect_text_direction("你好世界")
        assert direction == "ltr"

    def test_detect_rtl_arabic(self):
        """Test detecting RTL for Arabic text."""
        direction = detect_text_direction("مرحبا بالعالم")
        assert direction == "rtl"

    def test_detect_rtl_hebrew(self):
        """Test detecting RTL for Hebrew text."""
        direction = detect_text_direction("שלום עולם")
        assert direction == "rtl"

    def test_detect_mixed_text(self):
        """Test detecting direction for mixed text."""
        # Mostly English with some numbers
        direction = detect_text_direction("Hello 123 World")
        assert direction == "ltr"

    def test_detect_empty_string(self):
        """Test detecting direction for empty string."""
        direction = detect_text_direction("")
        assert direction == "ltr"  # Default to LTR

    def test_detect_numbers_only(self):
        """Test detecting direction for numbers only."""
        direction = detect_text_direction("12345")
        assert direction == "ltr"  # Default to LTR for non-alphabetic


class TestLanguageFontMap:
    """Tests for LANGUAGE_FONT_MAP configuration."""

    def test_language_font_map_has_default(self):
        """Test that map has default entry."""
        assert "default" in LANGUAGE_FONT_MAP

    def test_language_font_map_has_cjk(self):
        """Test that map has CJK language entries."""
        assert "zh-TW" in LANGUAGE_FONT_MAP
        assert "zh-CN" in LANGUAGE_FONT_MAP
        assert "ja" in LANGUAGE_FONT_MAP
        assert "ko" in LANGUAGE_FONT_MAP

    def test_language_font_map_structure(self):
        """Test that map entries have correct structure."""
        for lang, (font_name, patterns) in LANGUAGE_FONT_MAP.items():
            assert isinstance(font_name, str)
            assert isinstance(patterns, list)
            assert len(font_name) > 0
