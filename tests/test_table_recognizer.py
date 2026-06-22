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
