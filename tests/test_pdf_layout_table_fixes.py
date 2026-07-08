"""Regression tests for PDF layout rendering and table-context translation fixes.

Covers two defect clusters:

1. Layout rendering (blank / source-only / truncated output):
   - fit cascade measured CJK paragraphs as ONE line (word-wrap on spaces only),
     approving font sizes whose rendered lines were then silently dropped;
   - _truncate_to_fit reduced spaceless CJK text to a bare "…";
   - calculate_text_width under-measured CJK on the Helvetica fallback;
   - missing translations were whitened out (blank) or re-typeset as source;
   - side-by-side masked ALL element bboxes, blanking untranslated regions.

2. Table translation context:
   - PDF table cells were translated in isolation (no row/column context);
   - fitz merges whole table rows into one text block, destroying cell units;
   - unique_texts used set(), so sliding-context neighbors were random.
"""

from __future__ import annotations

import os
import tempfile
import unicodedata

import pytest

try:
    import fitz  # noqa: F401
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False


# ---------------------------------------------------------------------------
# Fixture PDFs
# ---------------------------------------------------------------------------

CJK_PARAGRAPH = (
    "品質管理系統應按計劃的時間間隔進行審查，以確保其持續的適用性、"
    "充分性和有效性，並與組織的策略方向保持一致。"
)


def _make_paragraph_pdf() -> str:
    """One-page PDF with a single English paragraph in a known bbox."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_textbox(
        fitz.Rect(50, 100, 400, 140),
        "The quality management system shall be reviewed at planned "
        "intervals to ensure its continuing suitability.",
        fontsize=10,
    )
    fd, path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    doc.save(path)
    doc.close()
    return path


TABLE_DATA = [
    ["Item", "Result", "Remark"],
    ["Surface", "Pass", "No defect"],
    ["Torque", "Fail", "Out of spec"],
]


def _make_table_pdf() -> str:
    """One-page PDF with a bordered 3×3 table plus a body paragraph."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_textbox(
        fitz.Rect(50, 40, 500, 70),
        "Inspection Report for incoming materials.",
        fontsize=11,
    )
    x0, y0, w, h = 50, 100, 150, 30
    for r in range(4):
        page.draw_line((x0, y0 + r * h), (x0 + 3 * w, y0 + r * h))
    for c in range(4):
        page.draw_line((x0 + c * w, y0), (x0 + c * w, y0 + 3 * h))
    for r in range(3):
        for c in range(3):
            page.insert_text((x0 + c * w + 5, y0 + r * h + 20), TABLE_DATA[r][c], fontsize=11)
    fd, path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    doc.save(path)
    doc.close()
    return path


def _parse(path: str):
    from app.backend.parsers.pdf_parser import PyMuPDFParser
    return PyMuPDFParser().parse(path)


BORDERLESS_TABLE_DATA = [
    ["Item", "Value", "Note"],
    ["Weight", "Value", "Note"],
    ["Height", "Value", "Note"],
]


def _make_borderless_table_pdf() -> str:
    """One-page PDF with a 3×3 grid of aligned text and NO ruling lines at
    all (fully borderless) — BR-101/AC-4: must be recovered via the looser-
    strategy find_tables() fallback (strategy='text'), since the default
    lines_strict strategy finds nothing without any drawn lines."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    x0, y0, w, h = 50, 100, 150, 30
    for r in range(3):
        for c in range(3):
            page.insert_text(
                (x0 + c * w + 5, y0 + r * h + 20), BORDERLESS_TABLE_DATA[r][c], fontsize=11,
            )
    fd, path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    doc.save(path)
    doc.close()
    return path


@pytest.fixture(autouse=True)
def _heuristic_layout(monkeypatch):
    """Force the heuristic layout path (no ONNX download in CI)."""
    monkeypatch.setenv("LAYOUT_DETECTOR_ENABLED", "false")


# ---------------------------------------------------------------------------
# 1. CJK-aware wrapping / truncation / width measurement
# ---------------------------------------------------------------------------


class TestCjkWrap:
    """_wrap_lines_simple must split spaceless runs at character level."""

    def test_cjk_paragraph_wraps_to_multiple_lines(self):
        from app.backend.renderers.text_region_renderer import _wrap_lines_simple

        text = CJK_PARAGRAPH * 4  # ~200 chars, no spaces
        lines = _wrap_lines_simple(text, "Helvetica", 12, 200)
        assert len(lines) > 5, (
            "A 200-char spaceless CJK paragraph in a 200pt-wide box must wrap "
            f"to many lines, got {len(lines)} — the pre-fix behavior was 1 line, "
            "which made the cascade approve sizes that truncated at render time."
        )

    def test_no_content_lost_by_wrapping(self):
        from app.backend.renderers.text_region_renderer import _wrap_lines_simple

        text = CJK_PARAGRAPH
        lines = _wrap_lines_simple(text, "Helvetica", 12, 100)
        assert "".join(lines) == text, "Character wrap must preserve every character"

    def test_latin_word_wrap_unchanged(self):
        from app.backend.renderers.text_region_renderer import _wrap_lines_simple

        text = "The quick brown fox jumps over the lazy dog"
        lines = _wrap_lines_simple(text, "Helvetica", 10, 120)
        # Words must not be split mid-word when they individually fit
        for line in lines:
            for word in line.split(" "):
                assert word in text.split(" "), f"word fragment {word!r} produced"

    def test_oversized_url_split_instead_of_overflowing(self):
        from app.backend.renderers.text_region_renderer import _wrap_lines_simple
        from app.backend.utils.font_utils import calculate_text_width

        url = "https://example.com/" + "a" * 120
        lines = _wrap_lines_simple(url, "Helvetica", 10, 100)
        assert len(lines) > 1
        for line in lines:
            assert calculate_text_width(line, "Helvetica", 10) <= 100 + 0.01


class TestCjkTruncate:
    """_truncate_to_fit must keep the fitting CJK prefix, not collapse to '…'."""

    def test_cjk_truncation_keeps_prefix(self):
        from app.backend.renderers.text_region_renderer import _truncate_to_fit

        text = CJK_PARAGRAPH * 4
        result = _truncate_to_fit(text, "Helvetica", 8, 1.0, 200, 40)
        assert result.endswith("…")
        assert len(result) > 20, (
            f"CJK truncation returned {result!r} — pre-fix behavior collapsed "
            "spaceless text to a bare ellipsis, blanking the block."
        )
        assert result[:-1] == text[: len(result) - 1], "must be a clean prefix"

    def test_latin_truncation_prefers_word_boundary(self):
        from app.backend.renderers.text_region_renderer import _truncate_to_fit

        text = "The quick brown fox jumps over the lazy dog repeatedly " * 10
        result = _truncate_to_fit(text, "Helvetica", 8, 1.0, 200, 40)
        assert result.endswith("…")
        body = result[:-1]
        # The cut must land on a word from the source, not mid-word
        assert body.split(" ")[-1] in text.split(), f"mid-word cut: {body[-20:]!r}"


class TestCjkWidthMeasurement:
    def test_helvetica_fallback_estimates_cjk_at_one_em(self):
        from app.backend.utils.font_utils import calculate_text_width

        text = "品質管理系統"
        w = calculate_text_width(text, "Helvetica", 12)
        assert w == pytest.approx(len(text) * 12, abs=0.01), (
            "CJK chars measured against a builtin Type1 font must count 1 em "
            "each; under-measuring made the cascade approve overflowing sizes."
        )


class TestCascadeRealism:
    def test_oversized_cjk_shrinks_or_truncates(self):
        """Cascade must NOT approve the initial size for text that cannot fit."""
        from app.backend.models.translatable_document import BoundingBox, StyleInfo
        from app.backend.renderers.text_region_renderer import fit_text_cascade

        text = CJK_PARAGRAPH * 4
        decision = fit_text_cascade(
            text,
            BoundingBox(x0=0, y0=0, x1=200, y1=40),
            StyleInfo(font_size=12, font_name="Helvetica"),
        )
        assert decision.font_size < 12 or decision.truncated, (
            "Pre-fix bug: a 200-char CJK paragraph in a 200×40 box was approved "
            "at the full initial size because it measured as one line."
        )
        if decision.truncated:
            assert len(decision.fitted_text) > 10, "truncation must keep a prefix"

    def test_short_cjk_fits_without_truncation(self):
        from app.backend.models.translatable_document import BoundingBox, StyleInfo
        from app.backend.renderers.text_region_renderer import fit_text_cascade

        decision = fit_text_cascade(
            "品質管理系統",
            BoundingBox(x0=0, y0=0, x1=300, y1=20),
            StyleInfo(font_size=11, font_name="Helvetica"),
        )
        assert not decision.truncated
        assert decision.fitted_text == "品質管理系統"


# ---------------------------------------------------------------------------
# 2. Overlay / side-by-side rendering behavior
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not HAS_PYMUPDF, reason="PyMuPDF not installed")
class TestOverlayRendering:
    def test_long_cjk_translation_fully_rendered(self):
        """The 截斷/空白 regression: the FULL translation must appear in output."""
        from app.backend.renderers.base import RenderMode
        from app.backend.renderers.fitz_renderer import PDFGenerator

        src = _make_paragraph_pdf()
        out = tempfile.mktemp(suffix=".pdf")
        try:
            doc = _parse(src)
            els = [e for e in doc.elements if e.should_translate and e.content.strip()]
            assert els, "fixture must yield a translatable element"
            translations = {e.content.strip(): CJK_PARAGRAPH for e in els}

            PDFGenerator(target_lang="zh-TW", draw_mask=True).generate(
                doc, translations, out, RenderMode.OVERLAY
            )

            rendered = fitz.open(out)[0].get_text().replace("\n", "")
            # Font cmaps may extract compatibility ideographs; normalize both sides.
            rendered = unicodedata.normalize("NFKC", rendered)
            expected = unicodedata.normalize("NFKC", CJK_PARAGRAPH)
            assert expected in rendered, (
                "Translated text truncated or missing in overlay output "
                f"(got {rendered[:120]!r})"
            )
            assert "quality management" not in rendered, "source text must be redacted"
        finally:
            for p in (src, out):
                if os.path.exists(p):
                    os.unlink(p)

    def test_missing_translation_keeps_source_visible(self):
        """No translation → original text must stay, not become a blank box."""
        from app.backend.renderers.base import RenderMode
        from app.backend.renderers.fitz_renderer import PDFGenerator

        src = _make_paragraph_pdf()
        out = tempfile.mktemp(suffix=".pdf")
        try:
            doc = _parse(src)
            PDFGenerator(target_lang="zh-TW", draw_mask=True).generate(
                doc, {}, out, RenderMode.OVERLAY
            )
            rendered = fitz.open(out)[0].get_text()
            assert "quality management" in rendered, (
                "Pre-fix behavior redacted the source and inserted a placeholder "
                "(or nothing), producing blank regions."
            )
        finally:
            for p in (src, out):
                if os.path.exists(p):
                    os.unlink(p)

    def test_side_by_side_missing_translation_not_blanked(self):
        """Right panel must keep source text for untranslated elements."""
        from app.backend.renderers.base import RenderMode
        from app.backend.renderers.fitz_renderer import PDFGenerator

        src = _make_paragraph_pdf()
        out = tempfile.mktemp(suffix=".pdf")
        try:
            doc = _parse(src)
            PDFGenerator(target_lang="zh-TW", draw_mask=True).generate(
                doc, {}, out, RenderMode.SIDE_BY_SIDE
            )
            rendered = fitz.open(out)[0].get_text()
            assert rendered.count("quality management") == 2, (
                "Untranslated element must remain visible on BOTH panels; "
                "pre-fix behavior white-masked it on the right panel."
            )
        finally:
            for p in (src, out):
                if os.path.exists(p):
                    os.unlink(p)


# ---------------------------------------------------------------------------
# 3. Table-context translation for PDF
# ---------------------------------------------------------------------------


TABLE_TRANSLATIONS = {
    "Item": "項目", "Result": "結果", "Remark": "備註",
    "Surface": "表面", "Pass": "合格", "No defect": "無缺陷",
    "Torque": "扭矩", "Fail": "不合格", "Out of spec": "超出規格",
}


class _StubTableClient:
    """Echoes the pipe-grid back translated via TABLE_TRANSLATIONS."""

    cache_model_key = "stub"

    def __init__(self):
        self.table_prompts = []
        self.flatten_texts = []

    @staticmethod
    def _build_table_translate_prompt(serialized, src, tgt):
        return "TABLE:\n" + serialized

    def translate_once(self, prompt, tgt, src, cancel_event=None, system_context=None):
        # cancel_event/system_context: additive, back-compatible LLMClient.translate_once
        # kwargs (qa-judge-hang-recovery / context-prefix-bleed-fix). This stub also serves
        # _translate_pdf_to_pdf's body-text path (translate_merged_paragraphs), not only the
        # direct table-context call site, so it must tolerate both.
        if prompt.startswith("TABLE:\n"):
            self.table_prompts.append(prompt)
            body = prompt.split("TABLE:\n", 1)[1]
            rows = []
            for line in body.split("\n"):
                rows.append(" | ".join(
                    TABLE_TRANSLATIONS.get(c.strip(), c.strip())
                    for c in line.split("|")
                ))
            return True, "\n".join(rows)
        self.flatten_texts.append(prompt)
        return True, "翻譯內容"


@pytest.mark.skipif(not HAS_PYMUPDF, reason="PyMuPDF not installed")
class TestPdfTableCellSplit:
    """Parser must yield one element per table CELL with grid coordinates."""

    def test_row_blocks_split_into_cells(self):
        src = _make_table_pdf()
        try:
            doc = _parse(src)
            cells = [e for e in doc.elements if e.metadata.get("table_id")]
            by_pos = {
                (e.metadata["table_row"], e.metadata["table_col"]): e
                for e in cells
                if e.metadata.get("table_row") is not None
            }
            x0, y0, w, h = 50, 100, 150, 30
            _pad = 2.0
            # Selection assertions: WHICH text landed in WHICH cell
            for r in range(3):
                for c in range(3):
                    elem = by_pos.get((r, c))
                    assert elem is not None and elem.content == TABLE_DATA[r][c], (
                        f"cell ({r},{c}) expected {TABLE_DATA[r][c]!r}, "
                        f"got {(elem.content if elem else None)!r} — fitz row-merged blocks "
                        "must be split into per-cell elements"
                    )
                    # BR-102 bbox-extent invariant regression guard (already
                    # applied by _split_elements_by_cells — NOT re-touched by
                    # this change): x1/y1 extend to the cell rect minus the
                    # 2.0pt border pad; x0/y0 stay at the tight text origin;
                    # metadata["lines"] preserves the pre-extension tight bbox.
                    cell_x1 = x0 + (c + 1) * w
                    cell_y1 = y0 + (r + 1) * h
                    assert elem.bbox.x1 == pytest.approx(cell_x1 - _pad), (
                        f"cell ({r},{c}) bbox.x1 must extend to the cell right edge minus pad"
                    )
                    assert elem.bbox.y1 == pytest.approx(cell_y1 - _pad), (
                        f"cell ({r},{c}) bbox.y1 must extend to the cell bottom edge minus pad"
                    )
                    lines = elem.metadata.get("lines")
                    assert lines, f"cell ({r},{c}) must carry metadata['lines'] for BR-84 whitening"
                    assert lines[0][0] == pytest.approx(elem.bbox.x0), "x0 must be unchanged by extension"
                    assert lines[0][1] == pytest.approx(elem.bbox.y0), "y0 must be unchanged by extension"
                    assert lines[0][2] <= elem.bbox.x1, "extension only grows x1, never shrinks it"
                    assert lines[0][3] <= elem.bbox.y1, "extension only grows y1, never shrinks it"
        finally:
            os.unlink(src)

    def test_body_text_not_marked_as_table(self):
        src = _make_table_pdf()
        try:
            doc = _parse(src)
            body = [e for e in doc.elements if "Inspection Report" in e.content]
            assert body and body[0].metadata.get("table_id") is None
        finally:
            os.unlink(src)


@pytest.mark.skipif(not HAS_PYMUPDF, reason="PyMuPDF not installed")
class TestTableDetectionFallbackIntegration:
    """AC-4 integration (BR-101): a real borderless-table PDF (no drawn ruling
    lines at all) is recovered via the looser-strategy find_tables() fallback."""

    def test_borderless_table_pdf_recovers_cells(self):
        src = _make_borderless_table_pdf()
        try:
            doc = _parse(src)
            cells = [e for e in doc.elements if e.metadata.get("table_id")]
            assert cells, (
                "the borderless 3x3 grid must be recovered via the BR-101 "
                "looser-strategy fallback — lines_strict alone finds nothing"
            )

            # Group by whatever row label the fallback grid assigned (PyMuPDF's
            # whitespace clustering need not label rows 0/1/2 exactly) — what
            # matters is that content is correctly grouped into 3 distinct rows
            # of 3 cells each, with no per-cell bbox spanning multiple columns.
            rows: dict = {}
            for e in cells:
                rows.setdefault(e.metadata.get("table_row"), []).append(e)

            assert len(rows) == 3, f"expected 3 distinct recovered rows, got {len(rows)}"
            expected_row_sets = [set(row) for row in BORDERLESS_TABLE_DATA]
            actual_row_sets = [
                {e.content for e in row_elems} for row_elems in rows.values()
            ]
            for expected in expected_row_sets:
                assert expected in actual_row_sets, (
                    f"expected row content {expected} not found among recovered "
                    f"rows {actual_row_sets}"
                )

            # Bug B symptom check: no per-cell bbox spans multiple original
            # columns (single column width is 150pt; a merged row would be ~450pt).
            for e in cells:
                assert e.bbox.x1 - e.bbox.x0 <= 200, (
                    f"cell {e.element_id!r} bbox spans multiple columns "
                    f"({e.bbox.x1 - e.bbox.x0:.1f}pt wide) — Bug B not fixed"
                )
        finally:
            os.unlink(src)


@pytest.mark.skipif(not HAS_PYMUPDF, reason="PyMuPDF not installed")
class TestWholeTableTranslation:
    def test_one_llm_call_per_table_with_full_grid(self):
        from app.backend.processors.pdf_processor import (
            _group_table_elements,
            _translate_pdf_tables_with_context,
        )

        src = _make_table_pdf()
        try:
            doc = _parse(src)
            translatable = [e for e in doc.elements if e.should_translate and e.content.strip()]
            groups = _group_table_elements(translatable)
            assert len(groups) == 1, "exactly one table group expected"

            stub = _StubTableClient()
            tmap = _translate_pdf_tables_with_context(groups, "zh-TW", "en", stub)

            assert len(stub.table_prompts) == 1, (
                "the whole table must be ONE LLM call, not one call per cell"
            )
            prompt = stub.table_prompts[0]
            # The prompt must serialize the full grid so each cell has context
            for row in TABLE_DATA:
                for cell_text in row:
                    assert cell_text in prompt
            # Every cell maps back to its own translation
            for src_text, tgt_text in TABLE_TRANSLATIONS.items():
                assert tmap.get(src_text) == tgt_text
        finally:
            os.unlink(src)

    def test_failed_table_call_falls_back_to_flatten(self):
        from app.backend.processors.pdf_processor import (
            _group_table_elements,
            _translate_pdf_tables_with_context,
        )

        src = _make_table_pdf()
        try:
            doc = _parse(src)
            translatable = [e for e in doc.elements if e.should_translate and e.content.strip()]
            groups = _group_table_elements(translatable)

            class _FailingClient:
                @staticmethod
                def _build_table_translate_prompt(serialized, src, tgt):
                    return "TABLE:\n" + serialized

                def translate_once(self, prompt, tgt, src):
                    return True, "not a grid at all"

            tmap = _translate_pdf_tables_with_context(groups, "zh-TW", "en", _FailingClient())
            assert tmap == {}, "unparseable grid → no mappings; cells stay in flatten path"
        finally:
            os.unlink(src)

    def test_end_to_end_pdf_output_uses_table_context(self):
        """Full _translate_pdf_to_pdf: table translated via grid, rendered in place."""
        from app.backend.processors.pdf_processor import _translate_pdf_to_pdf

        src = _make_table_pdf()
        out = tempfile.mktemp(suffix=".pdf")
        try:
            stub = _StubTableClient()
            stopped = _translate_pdf_to_pdf(
                src, out, ["zh-TW"], "en", stub, None, lambda s: None,
                skip_header_footer=False, layout_mode="overlay",
            )
            assert stopped is False
            assert len(stub.table_prompts) == 1

            rendered = unicodedata.normalize(
                "NFKC", fitz.open(out)[0].get_text()
            )
            for tgt_text in TABLE_TRANSLATIONS.values():
                assert tgt_text in rendered, f"cell translation {tgt_text!r} missing"
            for row in TABLE_DATA:
                for cell_text in row:
                    assert cell_text not in rendered, f"source {cell_text!r} not redacted"
        finally:
            for p in (src, out):
                if os.path.exists(p):
                    os.unlink(p)


# ---------------------------------------------------------------------------
# 4. Reading-order-preserving dedupe
# ---------------------------------------------------------------------------


class TestOrderPreservingDedupe:
    def test_pdf_processor_has_no_set_dedupe(self):
        """unique_texts must be built with dict.fromkeys (order-preserving)."""
        from pathlib import Path

        source = (
            Path(__file__).parent.parent
            / "app" / "backend" / "processors" / "pdf_processor.py"
        ).read_text(encoding="utf-8")
        assert "list(set(" not in source, (
            "list(set(...)) destroys reading order, feeding random neighbors to "
            "the sliding-context prompt; use list(dict.fromkeys(...))"
        )
        assert "dict.fromkeys" in source
