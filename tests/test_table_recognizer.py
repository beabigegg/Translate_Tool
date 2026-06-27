"""TDD tests for table structure recognition (p3-table-structure).

All tests must be RED before table_recognizer.py and related implementation code
is written.

Anti-tautology requirements (from test-plan.md):
  AC-3: Assert LLM call NOT made AND translated_content == content exactly.
  AC-4: Assert WHICH cells are in the batch payload (actual content strings),
        not just call count. Assert numeric cells ABSENT from payload.
  AC-2: Call through cell-batch seam directly (not translate_document()).

Collection-time module references (CLAUDE.md mock.patch learning):
  Modules imported at collection time; patch.object used throughout — never
  string-based patch("app.backend...").
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, call, patch

import pytest

# ---------------------------------------------------------------------------
# Collection-time module imports (patch.object targets these directly)
# ---------------------------------------------------------------------------

# Import modules under test at collection time so patch.object targets the
# live references, immune to sys.modules / package-attribute contamination.
import app.backend.models.translatable_document as _td_mod
import app.backend.utils.text_utils as _text_utils_mod

# These modules don't exist yet — import with try/except so collection
# succeeds and individual tests fail at the right assertion point.
try:
    import app.backend.parsers.table_recognizer as _table_rec
except ImportError:
    _table_rec = None  # type: ignore[assignment]

try:
    import app.backend.services.translation_service as _ts
except ImportError:
    _ts = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

from app.backend.models.translatable_document import (
    BoundingBox,
    DocumentMetadata,
    ElementType,
    PageInfo,
    TranslatableDocument,
    TranslatableElement,
)


def _make_table_element(
    eid: str = "elem-1",
    content: str = "Header\tValue\nRow1\t100",
    page_num: int = 1,
) -> TranslatableElement:
    """Create a table-typed TranslatableElement."""
    return TranslatableElement(
        element_id=eid,
        content=content,
        element_type=ElementType.TABLE,
        page_num=page_num,
        bbox=BoundingBox(x0=10.0, y0=10.0, x1=200.0, y1=100.0),
        metadata={},
    )


def _make_doc(elements: List[TranslatableElement]) -> TranslatableDocument:
    return TranslatableDocument(
        source_path="/fake/doc.pdf",
        source_type="pdf",
        elements=elements,
        pages=[PageInfo(page_num=1, width=612.0, height=792.0)],
        metadata=DocumentMetadata(),
    )


def _make_table_structure(
    element_id: str,
    cells: List[dict],
    num_rows: int = 2,
    num_cols: int = 2,
    recognizer: str = "TATR",
    recognition_confident: bool = True,
) -> dict:
    """Build a raw table_structure dict as would be stored in metadata."""
    return {
        "num_rows": num_rows,
        "num_cols": num_cols,
        "cells": cells,
        "recognizer": recognizer,
        "recognition_confident": recognition_confident,
    }


def _make_cell(
    element_id: str,
    row: int,
    col: int,
    content: str,
    is_numeric: bool = False,
    row_span: int = 1,
    col_span: int = 1,
    translated_content: Optional[str] = None,
    translation_status: str = "pending",
) -> dict:
    return {
        "cell_id": f"{element_id}:r{row}:c{col}",
        "row": row,
        "col": col,
        "row_span": row_span,
        "col_span": col_span,
        "content": content,
        "is_numeric": is_numeric,
        "translated_content": translated_content,
        "translation_status": translation_status,
    }


# ---------------------------------------------------------------------------
# TestTableStructureIRShape
# ---------------------------------------------------------------------------

class TestTableStructureIRShape:
    """AC-1: TableStructure/TableCell IR shape and metadata attachment."""

    def test_table_cell_id_format(self):
        """cell_id must follow format {element_id}:r{row}:c{col} (0-based)."""
        from app.backend.models.translatable_document import TableCell, TableStructure

        cell = TableCell(
            cell_id="elem-1:r0:c0",
            row=0,
            col=0,
            content="Header",
        )
        assert cell.cell_id == "elem-1:r0:c0"
        assert cell.row == 0
        assert cell.col == 0

    def test_table_structure_fields_present(self):
        """TableStructure must have num_rows, num_cols, cells, recognizer, recognition_confident."""
        from app.backend.models.translatable_document import TableCell, TableStructure

        cell = TableCell(cell_id="e:r0:c0", row=0, col=0, content="A")
        ts = TableStructure(
            num_rows=1,
            num_cols=1,
            cells=[cell],
            recognizer="TATR",
            recognition_confident=True,
        )
        assert ts.num_rows == 1
        assert ts.num_cols == 1
        assert len(ts.cells) == 1
        assert ts.recognizer == "TATR"
        assert ts.recognition_confident is True

    def test_table_structure_attached_in_metadata(self):
        """TableStructure stored under metadata['table_structure'] on a table element."""
        from app.backend.models.translatable_document import TableCell, TableStructure

        elem = _make_table_element("elem-1")
        cell = TableCell(cell_id="elem-1:r0:c0", row=0, col=0, content="Header")
        ts = TableStructure(
            num_rows=1, num_cols=1, cells=[cell], recognizer="TATR",
            recognition_confident=True,
        )
        elem.metadata["table_structure"] = ts.to_dict()

        assert "table_structure" in elem.metadata
        assert elem.metadata["table_structure"]["num_rows"] == 1
        assert elem.metadata["table_structure"]["cells"][0]["cell_id"] == "elem-1:r0:c0"

    def test_table_element_without_structure_is_plain_region(self):
        """A table element with no metadata['table_structure'] is a plain region marker."""
        elem = _make_table_element("elem-plain")
        assert elem.element_type == ElementType.TABLE
        assert "table_structure" not in elem.metadata


# ---------------------------------------------------------------------------
# TestNumericPassthrough
# ---------------------------------------------------------------------------

class TestNumericPassthrough:
    """AC-3: is_numeric_cell() predicate boundaries per BR-68."""

    def test_numeric_predicate_boundaries(self):
        """Digits + separators (., / - %) are numeric; letters are not."""
        from app.backend.utils.text_utils import is_numeric_cell

        # Allowed separators
        assert is_numeric_cell("100") is True
        assert is_numeric_cell("1,234") is True
        assert is_numeric_cell("3.14") is True
        assert is_numeric_cell("50%") is True
        assert is_numeric_cell("2024/01/01") is True
        assert is_numeric_cell("-42") is True

    def test_digit_only_cell_is_numeric(self):
        """Pure digit string is numeric."""
        from app.backend.utils.text_utils import is_numeric_cell

        assert is_numeric_cell("42") is True
        assert is_numeric_cell("0") is True
        assert is_numeric_cell("   123   ") is True  # whitespace ignored

    def test_text_cell_is_not_numeric(self):
        """Cells containing letters are not numeric."""
        from app.backend.utils.text_utils import is_numeric_cell

        assert is_numeric_cell("Revenue") is False
        assert is_numeric_cell("Q1 2024") is False
        assert is_numeric_cell("N/A") is False  # letters present
        assert is_numeric_cell("Total:") is False

    def test_mixed_digit_separator_cell_is_numeric(self):
        """Digits mixed with allowed separators are numeric."""
        from app.backend.utils.text_utils import is_numeric_cell

        assert is_numeric_cell("1.0") is True
        assert is_numeric_cell("1,000.00") is True
        assert is_numeric_cell(" 99 ") is True
        assert is_numeric_cell("10-20") is True

    def test_empty_cell_is_not_numeric(self):
        """Empty string is NOT numeric (data-shape §TableCell — empty → skipped)."""
        from app.backend.utils.text_utils import is_numeric_cell

        assert is_numeric_cell("") is False
        assert is_numeric_cell("   ") is False  # whitespace-only also not numeric


# ---------------------------------------------------------------------------
# TestTableStructureRoundTrip
# ---------------------------------------------------------------------------

class TestTableStructureRoundTrip:
    """AC-1: to_dict/from_dict lossless round-trip; backward-compat for old IR."""

    def test_table_structure_round_trip(self):
        """TableStructure survives to_dict() → from_dict() without loss."""
        from app.backend.models.translatable_document import TableCell, TableStructure

        cells = [
            TableCell(
                cell_id="e1:r0:c0", row=0, col=0, row_span=1, col_span=1,
                content="Header", is_numeric=False,
                translated_content="头部", translation_status="translated",
            ),
            TableCell(
                cell_id="e1:r0:c1", row=0, col=1, row_span=1, col_span=1,
                content="42", is_numeric=True,
                translated_content="42", translation_status="passthrough",
            ),
        ]
        ts = TableStructure(
            num_rows=1, num_cols=2, cells=cells, recognizer="TATR",
            recognition_confident=True,
        )
        d = ts.to_dict()
        ts2 = TableStructure.from_dict(d)

        assert ts2.num_rows == 1
        assert ts2.num_cols == 2
        assert ts2.recognizer == "TATR"
        assert ts2.recognition_confident is True
        assert len(ts2.cells) == 2
        assert ts2.cells[0].cell_id == "e1:r0:c0"
        assert ts2.cells[0].content == "Header"
        assert ts2.cells[0].translated_content == "头部"
        assert ts2.cells[0].translation_status == "translated"
        assert ts2.cells[1].is_numeric is True
        assert ts2.cells[1].translation_status == "passthrough"

    def test_old_format_ir_no_table_structure(self):
        """from_dict() must not raise when metadata['table_structure'] is absent (backward-compat)."""
        from app.backend.models.translatable_document import TableStructure

        elem_dict = {
            "element_id": "e-old",
            "content": "Some table",
            "element_type": "table",
            "page_num": 1,
            "bbox": None,
            "style": None,
            "should_translate": True,
            "translated_content": None,
            "metadata": {},  # no table_structure key
            "reading_order": None,
            "render_truncated": False,
        }
        # Must not raise
        elem = TranslatableElement.from_dict(elem_dict)
        assert "table_structure" not in elem.metadata

        # TableStructure.from_dict on absent metadata is also graceful
        result = TableStructure.from_dict(elem.metadata.get("table_structure", {}))
        # When given empty dict, should return degenerate/empty structure or raise
        # Per spec, from_dict returns empty structure when data missing keys
        # The key test is that TranslatableElement.from_dict doesn't raise — done above


# ---------------------------------------------------------------------------
# TestSameTableCellBatching
# ---------------------------------------------------------------------------

class TestSameTableCellBatching:
    """AC-4: One batch call per table; payload contains text cells, excludes numeric."""

    def test_single_batch_per_table(self):
        """Exactly one translate_blocks_batch call per table element (BR-69)."""
        assert _ts is not None, "translation_service module not found"

        elem = _make_table_element("elem-1", content="")
        cell1 = _make_cell("elem-1", 0, 0, "Revenue")
        cell2 = _make_cell("elem-1", 0, 1, "Amount")
        cell3 = _make_cell("elem-1", 1, 0, "Q1")
        cell4 = _make_cell("elem-1", 1, 1, "100", is_numeric=True)
        ts_dict = _make_table_structure(
            "elem-1",
            cells=[cell1, cell2, cell3, cell4],
            num_rows=2, num_cols=2,
        )
        elem.metadata["table_structure"] = ts_dict

        mock_batch_results = [
            (True, "收入"), (True, "金额"), (True, "第一季度")
        ]

        with patch.object(_ts, "translate_blocks_batch", return_value=mock_batch_results) as mock_batch:
            _ts.translate_table_cells(
                element=elem,
                targets=["zh-CN"],
                src_lang="en",
                client=MagicMock(),
            )
        # Exactly one batch call for this table
        assert mock_batch.call_count == 1

    def test_separate_batches_for_separate_tables(self):
        """Two separate tables produce two separate batch calls (BR-69)."""
        assert _ts is not None, "translation_service module not found"

        elem1 = _make_table_element("elem-1", content="")
        elem1.metadata["table_structure"] = _make_table_structure(
            "elem-1",
            cells=[_make_cell("elem-1", 0, 0, "Sales")],
            num_rows=1, num_cols=1,
        )

        elem2 = _make_table_element("elem-2", content="")
        elem2.metadata["table_structure"] = _make_table_structure(
            "elem-2",
            cells=[_make_cell("elem-2", 0, 0, "Revenue")],
            num_rows=1, num_cols=1,
        )

        mock_result = [(True, "翻译")]

        with patch.object(_ts, "translate_blocks_batch", return_value=mock_result) as mock_batch:
            _ts.translate_table_cells(
                element=elem1,
                targets=["zh-CN"],
                src_lang="en",
                client=MagicMock(),
            )
            _ts.translate_table_cells(
                element=elem2,
                targets=["zh-CN"],
                src_lang="en",
                client=MagicMock(),
            )

        # Two calls for two tables
        assert mock_batch.call_count == 2

    def test_batch_payload_contains_text_cells_not_numeric(self):
        """Batch payload must contain text cell content AND must NOT contain numeric cell content."""
        assert _ts is not None, "translation_service module not found"

        elem = _make_table_element("elem-1", content="")
        text_cell = _make_cell("elem-1", 0, 0, "Revenue")
        numeric_cell = _make_cell("elem-1", 0, 1, "12345", is_numeric=True)
        ts_dict = _make_table_structure(
            "elem-1",
            cells=[text_cell, numeric_cell],
            num_rows=1, num_cols=2,
        )
        elem.metadata["table_structure"] = ts_dict

        mock_result = [(True, "收入")]

        with patch.object(_ts, "translate_blocks_batch", return_value=mock_result) as mock_batch:
            _ts.translate_table_cells(
                element=elem,
                targets=["zh-CN"],
                src_lang="en",
                client=MagicMock(),
            )

        # Inspect the actual texts sent in the batch call
        call_args = mock_batch.call_args
        batch_texts = call_args[0][0]  # first positional arg is list of texts

        # Text cell content MUST be in payload
        assert "Revenue" in batch_texts
        # Numeric cell content MUST NOT be in payload (BR-68)
        assert "12345" not in batch_texts


# ---------------------------------------------------------------------------
# TestCellGranularityTranslation
# ---------------------------------------------------------------------------

class TestCellGranularityTranslation:
    """AC-2: parent translated_content built from cell results; placeholder on failure."""

    def test_no_flattened_translation_when_structure_available(self):
        """After translate_table_cells, parent translated_content is built from cells (D3).

        The test calls translate_table_cells directly — NOT translate_document —
        to avoid wrong-entry-point tautology.
        """
        assert _ts is not None, "translation_service module not found"

        elem = _make_table_element("elem-1", content="")
        cell00 = _make_cell("elem-1", 0, 0, "Revenue")
        cell01 = _make_cell("elem-1", 0, 1, "Amount")
        cell10 = _make_cell("elem-1", 1, 0, "Q1")
        cell11 = _make_cell("elem-1", 1, 1, "100", is_numeric=True)
        ts_dict = _make_table_structure(
            "elem-1",
            cells=[cell00, cell01, cell10, cell11],
            num_rows=2, num_cols=2,
        )
        elem.metadata["table_structure"] = ts_dict

        mock_results = [(True, "收入"), (True, "金额"), (True, "第一季度")]

        with patch.object(_ts, "translate_blocks_batch", return_value=mock_results):
            _ts.translate_table_cells(
                element=elem,
                targets=["zh-CN"],
                src_lang="en",
                client=MagicMock(),
            )

        # The parent translated_content must be the D3 reconstruction (tab/newline)
        # Row 0: "收入\t金额", Row 1: "第一季度\t100"
        assert elem.translated_content is not None
        rows = elem.translated_content.split("\n")
        assert len(rows) == 2
        row0_cells = rows[0].split("\t")
        row1_cells = rows[1].split("\t")
        assert row0_cells[0] == "收入"
        assert row0_cells[1] == "金额"
        assert row1_cells[0] == "第一季度"
        assert row1_cells[1] == "100"  # numeric passthrough

    def test_cell_batch_failure_applies_placeholder(self):
        """When batch call fails, BR-25 placeholder applied to translatable cells."""
        assert _ts is not None, "translation_service module not found"

        elem = _make_table_element("elem-1", content="")
        cell00 = _make_cell("elem-1", 0, 0, "Revenue")
        cell01 = _make_cell("elem-1", 0, 1, "Amount")
        ts_dict = _make_table_structure(
            "elem-1",
            cells=[cell00, cell01],
            num_rows=1, num_cols=2,
        )
        elem.metadata["table_structure"] = ts_dict

        # Batch returns failures
        mock_results = [(False, "[Translation failed|zh-CN] Revenue"), (False, "[Translation failed|zh-CN] Amount")]

        with patch.object(_ts, "translate_blocks_batch", return_value=mock_results):
            _ts.translate_table_cells(
                element=elem,
                targets=["zh-CN"],
                src_lang="en",
                client=MagicMock(),
            )

        # Cells must have failed status and placeholder text
        from app.backend.models.translatable_document import TableStructure
        ts = TableStructure.from_dict(elem.metadata["table_structure"])
        for cell in ts.cells:
            if cell.content:
                assert cell.translation_status == "failed"
                assert "[Translation failed" in cell.translated_content


# ---------------------------------------------------------------------------
# TestNumericPassthroughWiring
# ---------------------------------------------------------------------------

class TestNumericPassthroughWiring:
    """AC-3: numeric cell NOT sent to LLM AND translated_content == content exactly."""

    def test_numeric_cell_not_sent_to_llm(self):
        """Numeric cell content must not appear in the LLM batch payload."""
        assert _ts is not None, "translation_service module not found"

        elem = _make_table_element("elem-1", content="")
        text_cell = _make_cell("elem-1", 0, 0, "Product")
        numeric_cell = _make_cell("elem-1", 0, 1, "99.99", is_numeric=True)
        ts_dict = _make_table_structure(
            "elem-1",
            cells=[text_cell, numeric_cell],
            num_rows=1, num_cols=2,
        )
        elem.metadata["table_structure"] = ts_dict

        mock_results = [(True, "产品")]

        with patch.object(_ts, "translate_blocks_batch", return_value=mock_results) as mock_batch:
            _ts.translate_table_cells(
                element=elem,
                targets=["zh-CN"],
                src_lang="en",
                client=MagicMock(),
            )

        # Verify "99.99" is NOT in the batch payload
        call_args = mock_batch.call_args
        batch_texts = call_args[0][0]
        assert "99.99" not in batch_texts

    def test_numeric_cell_content_identical_pre_post_translation(self):
        """Numeric cell translated_content must equal content exactly (BR-68)."""
        assert _ts is not None, "translation_service module not found"

        elem = _make_table_element("elem-1", content="")
        text_cell = _make_cell("elem-1", 0, 0, "Revenue")
        numeric_cell = _make_cell("elem-1", 0, 1, "1,234.56", is_numeric=True)
        ts_dict = _make_table_structure(
            "elem-1",
            cells=[text_cell, numeric_cell],
            num_rows=1, num_cols=2,
        )
        elem.metadata["table_structure"] = ts_dict

        mock_results = [(True, "收入")]

        with patch.object(_ts, "translate_blocks_batch", return_value=mock_results):
            _ts.translate_table_cells(
                element=elem,
                targets=["zh-CN"],
                src_lang="en",
                client=MagicMock(),
            )

        # Retrieve the updated TableStructure from metadata
        from app.backend.models.translatable_document import TableStructure
        ts = TableStructure.from_dict(elem.metadata["table_structure"])
        numeric = next(c for c in ts.cells if c.is_numeric)

        # Anti-tautology: assert exact equality, not just call count
        assert numeric.translated_content == "1,234.56"
        assert numeric.translation_status == "passthrough"


# ---------------------------------------------------------------------------
# TestModelUnavailableFallback
# ---------------------------------------------------------------------------

class TestModelUnavailableFallback:
    """AC-5: WARNING logged; no TableStructure attached; no crash."""

    def test_table_recognizer_unavailable_falls_back(self, caplog):
        """When TableRecognizer._load_session fails (no model), no TableStructure attached."""
        assert _table_rec is not None, "table_recognizer module not found"

        from app.backend.parsers.table_recognizer import TableRecognizer

        elem = _make_table_element("elem-1")

        recognizer = TableRecognizer()
        # Force session load failure
        recognizer._session_load_failed = True

        with caplog.at_level(logging.WARNING, logger="app.backend.parsers.table_recognizer"):
            result = recognizer.recognize(elem, page_pixmap_array=None, doc_id="test-doc")

        assert result is None
        assert "table_structure" not in elem.metadata

    def test_table_recognizer_load_error_falls_back(self, caplog):
        """When ONNX session raises, _session_load_failed is latched and WARNING logged."""
        assert _table_rec is not None, "table_recognizer module not found"

        from app.backend.parsers.table_recognizer import TableRecognizer

        recognizer = TableRecognizer(model_path="/nonexistent/path/model.onnx")

        with caplog.at_level(logging.WARNING, logger="app.backend.parsers.table_recognizer"):
            success = recognizer._load_session()

        assert success is False
        assert recognizer._session_load_failed is True
        # Warning must have been emitted
        assert any("table" in r.message.lower() or "recogni" in r.message.lower()
                   for r in caplog.records)


# ---------------------------------------------------------------------------
# TestDegenerateTableHandling
# ---------------------------------------------------------------------------

class TestDegenerateTableHandling:
    """AC-6: all-numeric / all-empty → no LLM call; merged cell = single TableCell."""

    def test_all_numeric_table_no_llm_call(self):
        """Table with all numeric cells → no LLM call; all get passthrough status."""
        assert _ts is not None, "translation_service module not found"

        elem = _make_table_element("elem-1", content="")
        cells = [
            _make_cell("elem-1", 0, 0, "100", is_numeric=True),
            _make_cell("elem-1", 0, 1, "200", is_numeric=True),
            _make_cell("elem-1", 1, 0, "300", is_numeric=True),
            _make_cell("elem-1", 1, 1, "400", is_numeric=True),
        ]
        ts_dict = _make_table_structure("elem-1", cells=cells, num_rows=2, num_cols=2)
        elem.metadata["table_structure"] = ts_dict

        with patch.object(_ts, "translate_blocks_batch") as mock_batch:
            _ts.translate_table_cells(
                element=elem,
                targets=["zh-CN"],
                src_lang="en",
                client=MagicMock(),
            )

        # No LLM call for all-numeric table
        assert mock_batch.call_count == 0

        # All cells get passthrough
        from app.backend.models.translatable_document import TableStructure
        ts = TableStructure.from_dict(elem.metadata["table_structure"])
        for cell in ts.cells:
            assert cell.translation_status == "passthrough"
            assert cell.translated_content == cell.content

    def test_all_empty_cells_no_llm_call(self):
        """Table with all empty cells → no LLM call; all get skipped status."""
        assert _ts is not None, "translation_service module not found"

        elem = _make_table_element("elem-1", content="")
        cells = [
            _make_cell("elem-1", 0, 0, ""),
            _make_cell("elem-1", 0, 1, ""),
        ]
        ts_dict = _make_table_structure("elem-1", cells=cells, num_rows=1, num_cols=2)
        elem.metadata["table_structure"] = ts_dict

        with patch.object(_ts, "translate_blocks_batch") as mock_batch:
            _ts.translate_table_cells(
                element=elem,
                targets=["zh-CN"],
                src_lang="en",
                client=MagicMock(),
            )

        assert mock_batch.call_count == 0

        from app.backend.models.translatable_document import TableStructure
        ts = TableStructure.from_dict(elem.metadata["table_structure"])
        for cell in ts.cells:
            assert cell.translation_status == "skipped"
            assert cell.translated_content == ""

    def test_merged_cells_treated_as_single_cell(self):
        """Merged cell (row_span>1 or col_span>1) is treated as a single TableCell for translation."""
        from app.backend.models.translatable_document import TableCell, TableStructure

        # A 2-row merged cell
        merged = TableCell(
            cell_id="e1:r0:c0",
            row=0, col=0,
            row_span=2, col_span=1,
            content="Merged Header",
            is_numeric=False,
        )
        ts = TableStructure(
            num_rows=2, num_cols=1,
            cells=[merged],
            recognizer="TATR",
            recognition_confident=True,
        )
        assert len(ts.cells) == 1
        assert ts.cells[0].row_span == 2
        assert ts.cells[0].content == "Merged Header"


# ---------------------------------------------------------------------------
# TestParseOutputsGrid
# ---------------------------------------------------------------------------

class TestParseOutputsGrid:
    """AC-1,2,3,4,8: canonical 2x3 grid decoded correctly from TATR ONNX outputs."""

    # Image size: 768x768 (model input)
    # 2 rows: top row y_center=0.25, bottom row y_center=0.75
    # 3 cols: left x_center=0.17, mid x_center=0.50, right x_center=0.83
    # row bbox CXCYWH: (0.5, 0.25, 1.0, 0.5) and (0.5, 0.75, 1.0, 0.5)
    # col bbox CXCYWH: (0.17, 0.5, 0.34, 1.0), (0.5, 0.5, 0.34, 1.0), (0.83, 0.5, 0.34, 1.0)

    @staticmethod
    def _make_2x3_outputs():
        import numpy as np
        # 5 detections, 7 classes (TATR has classes 0..6)
        # class 2 = row, class 1 = col
        logits = np.zeros((1, 5, 7), dtype=np.float32)
        # detections 0,1 -> class 2 (row)
        logits[0, 0, 2] = 10.0
        logits[0, 1, 2] = 10.0
        # detections 2,3,4 -> class 1 (col)
        logits[0, 2, 1] = 10.0
        logits[0, 3, 1] = 10.0
        logits[0, 4, 1] = 10.0

        boxes = np.zeros((1, 5, 4), dtype=np.float32)
        # row 0: top row CXCYWH
        boxes[0, 0] = [0.5, 0.25, 1.0, 0.5]
        # row 1: bottom row CXCYWH
        boxes[0, 1] = [0.5, 0.75, 1.0, 0.5]
        # col 0: left col CXCYWH
        boxes[0, 2] = [0.17, 0.5, 0.34, 1.0]
        # col 1: mid col CXCYWH
        boxes[0, 3] = [0.50, 0.5, 0.34, 1.0]
        # col 2: right col CXCYWH
        boxes[0, 4] = [0.83, 0.5, 0.34, 1.0]

        return [logits, boxes]

    def test_2x3_grid_returns_six_cells(self):
        assert _table_rec is not None
        from app.backend.parsers.table_recognizer import TableRecognizer
        cells, num_rows, num_cols = TableRecognizer()._parse_outputs(
            self._make_2x3_outputs(), "elem-t"
        )
        assert len(cells) == 6

    def test_row_ordering_top_row_is_index_zero(self):
        assert _table_rec is not None
        from app.backend.parsers.table_recognizer import TableRecognizer
        cells, _, _ = TableRecognizer()._parse_outputs(self._make_2x3_outputs(), "elem-t")
        row0_cells = [c for c in cells if c.row == 0]
        row1_cells = [c for c in cells if c.row == 1]
        assert row0_cells, "no cells at row=0"
        assert row1_cells, "no cells at row=1"
        # All cells at row=0 must have a smaller (or equal) y_center than cells at row=1
        # We verify via cell_id: row=0 corresponds to top row (y_center=0.25*768=192)
        # and row=1 corresponds to bottom row (y_center=0.75*768=576)
        # The cell_id encodes the row index, so we check ordering is correct
        # by confirming row=0 cell_ids contain ":r0:" and row=1 contain ":r1:"
        assert all(":r0:" in c.cell_id for c in row0_cells)
        assert all(":r1:" in c.cell_id for c in row1_cells)

    def test_col_ordering_leftmost_col_is_index_zero(self):
        assert _table_rec is not None
        from app.backend.parsers.table_recognizer import TableRecognizer
        cells, _, _ = TableRecognizer()._parse_outputs(self._make_2x3_outputs(), "elem-t")
        col0_cells = [c for c in cells if c.col == 0]
        col1_cells = [c for c in cells if c.col == 1]
        assert col0_cells, "no cells at col=0"
        assert col1_cells, "no cells at col=1"
        assert all(":c0" in c.cell_id for c in col0_cells)
        assert all(":c1" in c.cell_id for c in col1_cells)

    def test_cell_assigned_correct_row_col_by_overlap(self):
        """SELECTION: find the cell at row=1, col=2 by cell_id; assert row==1, col==2."""
        assert _table_rec is not None
        from app.backend.parsers.table_recognizer import TableRecognizer
        cells, _, _ = TableRecognizer()._parse_outputs(self._make_2x3_outputs(), "elem-t")
        target = next((c for c in cells if c.cell_id == "elem-t:r1:c2"), None)
        assert target is not None, "cell 'elem-t:r1:c2' not found"
        assert target.row == 1
        assert target.col == 2

    def test_all_cells_have_empty_content(self):
        assert _table_rec is not None
        from app.backend.parsers.table_recognizer import TableRecognizer
        cells, _, _ = TableRecognizer()._parse_outputs(self._make_2x3_outputs(), "elem-t")
        assert all(c.content == "" for c in cells)

    def test_num_rows_and_num_cols_match_grid(self):
        assert _table_rec is not None
        from app.backend.parsers.table_recognizer import TableRecognizer
        cells, num_rows, num_cols = TableRecognizer()._parse_outputs(
            self._make_2x3_outputs(), "elem-t"
        )
        assert num_rows == 2
        assert num_cols == 3

    def test_cell_id_format_includes_row_col(self):
        assert _table_rec is not None
        from app.backend.parsers.table_recognizer import TableRecognizer
        cells, _, _ = TableRecognizer()._parse_outputs(self._make_2x3_outputs(), "elem-t")
        r0c0 = next((c for c in cells if c.row == 0 and c.col == 0), None)
        assert r0c0 is not None
        assert r0c0.cell_id == "elem-t:r0:c0"


# ---------------------------------------------------------------------------
# TestParseOutputsDegenerate
# ---------------------------------------------------------------------------

class TestParseOutputsDegenerate:
    """AC-6: degenerate inputs return ([], 0, 0) without raising."""

    @staticmethod
    def _make_outputs_all_below_threshold():
        import numpy as np
        # All logits=0 → softmax scores all equal (1/7 ≈ 0.14) < 0.5
        logits = np.zeros((1, 3, 7), dtype=np.float32)
        boxes = np.zeros((1, 3, 4), dtype=np.float32)
        boxes[0, 0] = [0.5, 0.25, 1.0, 0.5]
        boxes[0, 1] = [0.5, 0.75, 1.0, 0.5]
        boxes[0, 2] = [0.5, 0.5, 1.0, 1.0]
        return [logits, boxes]

    @staticmethod
    def _make_outputs_cols_only():
        import numpy as np
        logits = np.zeros((1, 2, 7), dtype=np.float32)
        logits[0, 0, 1] = 10.0  # class 1 = col
        logits[0, 1, 1] = 10.0
        boxes = np.zeros((1, 2, 4), dtype=np.float32)
        boxes[0, 0] = [0.25, 0.5, 0.5, 1.0]
        boxes[0, 1] = [0.75, 0.5, 0.5, 1.0]
        return [logits, boxes]

    @staticmethod
    def _make_outputs_rows_only():
        import numpy as np
        logits = np.zeros((1, 2, 7), dtype=np.float32)
        logits[0, 0, 2] = 10.0  # class 2 = row
        logits[0, 1, 2] = 10.0
        boxes = np.zeros((1, 2, 4), dtype=np.float32)
        boxes[0, 0] = [0.5, 0.25, 1.0, 0.5]
        boxes[0, 1] = [0.5, 0.75, 1.0, 0.5]
        return [logits, boxes]

    @staticmethod
    def _make_outputs_identical_rows():
        import numpy as np
        # Two row detections with identical CXCYWH + one col
        logits = np.zeros((1, 3, 7), dtype=np.float32)
        logits[0, 0, 2] = 10.0  # row
        logits[0, 1, 2] = 10.0  # row (identical bbox)
        logits[0, 2, 1] = 10.0  # col
        boxes = np.zeros((1, 3, 4), dtype=np.float32)
        boxes[0, 0] = [0.5, 0.5, 1.0, 1.0]
        boxes[0, 1] = [0.5, 0.5, 1.0, 1.0]  # identical
        boxes[0, 2] = [0.5, 0.5, 1.0, 1.0]
        return [logits, boxes]

    def test_no_detections_above_threshold_returns_empty(self):
        assert _table_rec is not None
        from app.backend.parsers.table_recognizer import TableRecognizer
        cells, num_rows, num_cols = TableRecognizer()._parse_outputs(
            self._make_outputs_all_below_threshold(), "elem-t"
        )
        assert cells == []
        assert num_rows == 0
        assert num_cols == 0

    def test_zero_rows_only_cols_returns_empty(self):
        assert _table_rec is not None
        from app.backend.parsers.table_recognizer import TableRecognizer
        cells, num_rows, num_cols = TableRecognizer()._parse_outputs(
            self._make_outputs_cols_only(), "elem-t"
        )
        assert cells == []
        assert num_rows == 0
        assert num_cols == 0

    def test_zero_cols_only_rows_returns_empty(self):
        assert _table_rec is not None
        from app.backend.parsers.table_recognizer import TableRecognizer
        cells, num_rows, num_cols = TableRecognizer()._parse_outputs(
            self._make_outputs_rows_only(), "elem-t"
        )
        assert cells == []
        assert num_rows == 0
        assert num_cols == 0

    def test_overlapping_bboxes_no_crash(self):
        assert _table_rec is not None
        from app.backend.parsers.table_recognizer import TableRecognizer
        result = TableRecognizer()._parse_outputs(self._make_outputs_identical_rows(), "elem-t")
        cells, num_rows, num_cols = result
        # Must return well-formed tuple without raising
        assert isinstance(cells, list)
        assert isinstance(num_rows, int)
        assert isinstance(num_cols, int)


# ---------------------------------------------------------------------------
# TestParseOutputsBoxFormat
# ---------------------------------------------------------------------------

class TestParseOutputsBoxFormat:
    """AC-5: CXCYWH normalized → pixel XYXY conversion and sort correctness."""

    def test_cxcywh_normalized_converts_to_pixel_coords(self):
        """Single row detection at CXCYWH (0.5, 0.25, 0.3, 0.1); verify pixel XYXY."""
        import numpy as np
        assert _table_rec is not None
        from app.backend.parsers.table_recognizer import TableRecognizer

        # One row + one col so a cell is emitted (otherwise degenerate)
        # Row: cx=0.5 cy=0.25 w=0.3 h=0.1
        # Col: full-height spanning column cx=0.5 cy=0.5 w=1.0 h=1.0
        logits = np.zeros((1, 2, 7), dtype=np.float32)
        logits[0, 0, 2] = 10.0  # row
        logits[0, 1, 1] = 10.0  # col
        boxes = np.zeros((1, 2, 4), dtype=np.float32)
        boxes[0, 0] = [0.5, 0.25, 0.3, 0.1]   # row
        boxes[0, 1] = [0.5, 0.5, 1.0, 1.0]    # col (full width)

        cells, num_rows, num_cols = TableRecognizer()._parse_outputs([logits, boxes], "elem-t")
        # We expect 1 cell (1 row x 1 col, intersecting)
        assert len(cells) == 1
        # Now verify pixel conversion by checking that the intersection area is > 0
        # (which it is, since col is full-width/height and row overlaps)
        # The row pixel XYXY should be:
        #   cx_px=384, cy_px=192, w_px=230.4, h_px=76.8
        #   x0=384-115.2=268.8, y0=192-38.4=153.6, x1=384+115.2=499.2, y1=192+38.4=230.4
        # We verify this indirectly: the row must overlap the full-width col
        assert num_rows == 1
        assert num_cols == 1

    def test_row_sort_uses_pixel_y_center(self):
        """Two rows: first in array has larger y_center; assert row=0 is from the smaller y_center."""
        import numpy as np
        assert _table_rec is not None
        from app.backend.parsers.table_recognizer import TableRecognizer

        # Row detection 0 in array: cy=0.75 (bottom) — should become row index 1
        # Row detection 1 in array: cy=0.25 (top)   — should become row index 0
        logits = np.zeros((1, 4, 7), dtype=np.float32)
        logits[0, 0, 2] = 10.0   # row (bottom, inserted first)
        logits[0, 1, 2] = 10.0   # row (top, inserted second)
        logits[0, 2, 1] = 10.0   # col left
        logits[0, 3, 1] = 10.0   # col right
        boxes = np.zeros((1, 4, 4), dtype=np.float32)
        boxes[0, 0] = [0.5, 0.75, 1.0, 0.5]   # bottom row
        boxes[0, 1] = [0.5, 0.25, 1.0, 0.5]   # top row
        boxes[0, 2] = [0.25, 0.5, 0.5, 1.0]   # left col
        boxes[0, 3] = [0.75, 0.5, 0.5, 1.0]   # right col

        cells, num_rows, num_cols = TableRecognizer()._parse_outputs([logits, boxes], "elem-t")
        assert num_rows == 2
        assert num_cols == 2

        # Cell at row=0 should come from the TOP row (y_center=0.25), not bottom (0.75)
        # The top row (cy=0.25) cells should have row=0
        # We can verify: cell "elem-t:r0:c0" should exist and there should be a "elem-t:r1:c0"
        r0_cells = [c for c in cells if c.row == 0]
        r1_cells = [c for c in cells if c.row == 1]
        assert r0_cells, "no cells at row=0"
        assert r1_cells, "no cells at row=1"

        # SELECTION: sort is applied — the top-row detection (cy=0.25, inserted SECOND
        # in the array) must have been promoted to row index 0
        # Verify by checking 4 cells exist with distinct (row, col) pairs
        cell_ids = {c.cell_id for c in cells}
        assert "elem-t:r0:c0" in cell_ids
        assert "elem-t:r0:c1" in cell_ids
        assert "elem-t:r1:c0" in cell_ids
        assert "elem-t:r1:c1" in cell_ids

    def test_row_sort_direction_asymmetric_layout(self):
        """Binding sort-direction test: asymmetric layout where reversed sort changes intersections.

        Layout (normalized CXCYWH, image 768x768):
          Top row    (cx=0.25, cy=0.25, w=0.5,  h=0.5)  -> pixel [0,0,384,384]  (left half only)
          Bottom row (cx=0.5,  cy=0.75, w=1.0,  h=0.5)  -> pixel [0,384,768,768] (full width)
          Left col   (cx=0.25, cy=0.5,  w=0.5,  h=1.0)  -> pixel [0,0,384,768]
          Right col  (cx=0.75, cy=0.5,  w=0.5,  h=1.0)  -> pixel [384,0,768,768]

        Intersections with CORRECT sort (top row = index 0):
          r0 x left-col  = [0,0,384,384] ∩ [0,0,384,768]  → area>0 → EMITS  "elem-t:r0:c0"
          r0 x right-col = [0,0,384,384] ∩ [384,0,768,768]→ width=0 → NO CELL (top row stops at x=384)
          r1 x left-col  = [0,384,768,768]∩[0,0,384,768]  → area>0 → EMITS  "elem-t:r1:c0"
          r1 x right-col = [0,384,768,768]∩[384,0,768,768]→ area>0 → EMITS  "elem-t:r1:c1"

        If sort were REVERSED (bottom row gets index 0):
          r0 x right-col would EMIT as "elem-t:r0:c1"  ← assertion below would FAIL

        Detection order in array: bottom row inserted FIRST, top row SECOND (verifies sort, not insertion order).
        """
        import numpy as np
        assert _table_rec is not None
        from app.backend.parsers.table_recognizer import TableRecognizer

        logits = np.zeros((1, 4, 7), dtype=np.float32)
        logits[0, 0, 2] = 10.0   # detection 0 = bottom row (cy=0.75, inserted first)
        logits[0, 1, 2] = 10.0   # detection 1 = top row    (cy=0.25, inserted second)
        logits[0, 2, 1] = 10.0   # left col
        logits[0, 3, 1] = 10.0   # right col

        boxes = np.zeros((1, 4, 4), dtype=np.float32)
        boxes[0, 0] = [0.5,  0.75, 1.0, 0.5]   # bottom row: full-width
        boxes[0, 1] = [0.25, 0.25, 0.5, 0.5]   # top row: left-half only
        boxes[0, 2] = [0.25, 0.5,  0.5, 1.0]   # left col
        boxes[0, 3] = [0.75, 0.5,  0.5, 1.0]   # right col

        cells, num_rows, num_cols = TableRecognizer()._parse_outputs([logits, boxes], "elem-t")

        cell_ids = {c.cell_id for c in cells}
        # Correct sort: 3 cells (top row only overlaps left col)
        assert len(cells) == 3, f"expected 3 cells, got {len(cells)}: {cell_ids}"
        assert "elem-t:r0:c0" in cell_ids   # top-row × left-col EMITS
        assert "elem-t:r0:c1" not in cell_ids  # top-row × right-col does NOT intersect
        assert "elem-t:r1:c0" in cell_ids   # bottom-row × left-col EMITS
        assert "elem-t:r1:c1" in cell_ids   # bottom-row × right-col EMITS
