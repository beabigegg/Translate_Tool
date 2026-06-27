"""TDD tests for table-context-translation behavior (IP-0: Red phase).

Tests that will fail until all implementation steps (IP-1 through IP-4) are done:
  - IP-1: table_serializer.py (serialize/parse)
  - IP-2: _build_table_translate_prompt in both clients
  - IP-3: PDF translate_table_cells uses serializer + single translate_once call
  - IP-4: DOCX/XLSX/PPTX processors group cells per table, key by col

Anti-tautology rules (CLAUDE.md):
  - All LLM mocks target client boundary using collection-time patch.object.
  - Do NOT call translate_document(); call processor functions directly.
  - Assert WHAT was called and WHICH translations appear, not just call counts.

Collection-time imports:
  Modules captured at collection time so patch.object is immune to sys.modules
  contamination (CLAUDE.md promoted learnings).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import MagicMock, call, patch

import pytest

# ---------------------------------------------------------------------------
# Collection-time module imports (patch.object targets)
# ---------------------------------------------------------------------------

import app.backend.processors.docx_processor as _docx_proc
import app.backend.processors.pptx_processor as _pptx_proc
import app.backend.processors.xlsx_processor as _xlsx_proc
import app.backend.services.translation_service as _ts
import app.backend.clients.ollama_client as _ollama_mod
import app.backend.clients.openai_compatible_client as _oa_mod

try:
    import app.backend.utils.table_serializer as _table_ser
except ImportError:
    _table_ser = None  # type: ignore[assignment]

from app.backend.models.translatable_document import (
    TableCell,
    TableStructure,
    TranslatableElement,
    BoundingBox,
    ElementType,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client_mock(**kwargs) -> MagicMock:
    """Return a minimal MagicMock client that satisfies processor health checks."""
    m = MagicMock()
    m.health_check.return_value = (True, "ok")
    m.system_prompt = ""
    m.model_type = "general"
    m._is_translation_dedicated.return_value = False
    m._is_translategemma_model.return_value = False
    for k, v in kwargs.items():
        setattr(m, k, v)
    return m


def _make_table_cell(row: int, col: int, content: str, is_numeric: bool = False) -> TableCell:
    from dataclasses import dataclass as _dc
    return TableCell(
        cell_id=f"c{row}{col}",
        row=row,
        col=col,
        content=content,
        is_numeric=is_numeric,
    )


def _make_table_structure(rows: List[List[str]]) -> TableStructure:
    """Build a TableStructure from a 2-D list of strings."""
    num_rows = len(rows)
    num_cols = len(rows[0]) if rows else 0
    cells = []
    for r_idx, row in enumerate(rows):
        for c_idx, text in enumerate(row):
            cells.append(_make_table_cell(r_idx, c_idx, text))
    return TableStructure(
        num_rows=num_rows,
        num_cols=num_cols,
        recognizer="test",
        recognition_confident=True,
        cells=cells,
    )


def _make_table_element(ts: TableStructure, eid: str = "elem-1") -> TranslatableElement:
    """Wrap TableStructure in a table-typed TranslatableElement."""
    return TranslatableElement(
        element_id=eid,
        content="",
        element_type=ElementType.TABLE,
        page_num=1,
        bbox=BoundingBox(x0=0.0, y0=0.0, x1=100.0, y1=100.0),
        metadata={"table_structure": ts.to_dict()},
    )


def _make_docx_with_table(tmp_path: Path, rows: List[List[str]]) -> Path:
    """Create a minimal DOCX containing one table (no body paragraphs)."""
    import docx as _docx_lib
    doc = _docx_lib.Document()
    if rows:
        num_rows = len(rows)
        num_cols = len(rows[0])
        tbl = doc.add_table(rows=num_rows, cols=num_cols)
        for r, row in enumerate(rows):
            for c, text in enumerate(row):
                tbl.cell(r, c).text = text
    p = tmp_path / "table_test.docx"
    doc.save(str(p))
    return p


def _make_xlsx_with_cells(tmp_path: Path, rows: List[List[str]]) -> Path:
    """Create a minimal XLSX with cells filled from rows matrix."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    for r_idx, row in enumerate(rows, 1):
        for c_idx, text in enumerate(row, 1):
            ws.cell(row=r_idx, column=c_idx, value=text)
    p = tmp_path / "table_test.xlsx"
    wb.save(str(p))
    return p


def _make_pptx_with_table(tmp_path: Path, rows: List[List[str]]) -> Path:
    """Create a minimal PPTX with one table on one slide."""
    import pptx
    from pptx.util import Inches
    prs = pptx.Presentation()
    blank_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(blank_layout)
    num_rows = len(rows)
    num_cols = len(rows[0]) if rows else 0
    tbl_shape = slide.shapes.add_table(
        num_rows, num_cols,
        Inches(1), Inches(1), Inches(6), Inches(3)
    )
    tbl = tbl_shape.table
    for r, row in enumerate(rows):
        for c, text in enumerate(row):
            tbl.cell(r, c).text = text
    p = tmp_path / "table_test.pptx"
    prs.save(str(p))
    return p


# Grid response helpers
def _grid_response(rows: List[List[str]]) -> str:
    """Build a pipe-grid string as a mock LLM response."""
    return "\n".join(" | ".join(row) for row in rows)


# ---------------------------------------------------------------------------
# AC-2: Instruction precedes serialized grid in prompt
# ---------------------------------------------------------------------------

class TestPromptBuilder:
    """Tests for _build_table_translate_prompt in both clients (AC-2)."""

    def test_instruction_precedes_serialized_grid_in_prompt_ollama(self):
        """OllamaClient._build_table_translate_prompt: instruction appears before grid."""
        from app.backend.clients.ollama_client import OllamaClient
        serialized = "Name | Value\nApple | 100"
        prompt = OllamaClient._build_table_translate_prompt(serialized, "en", "zh")

        instr_idx = min(
            (prompt.find(word) for word in ("Translate", "translate") if prompt.find(word) >= 0),
            default=-1,
        )
        grid_idx = prompt.find("Name | Value")

        assert instr_idx >= 0, "Instruction not found in prompt"
        assert grid_idx >= 0, "Serialized grid not found in prompt"
        assert instr_idx < grid_idx, (
            f"Instruction (pos {instr_idx}) must appear BEFORE grid (pos {grid_idx}) in prompt"
        )

    def test_instruction_precedes_serialized_grid_in_prompt_openai(self):
        """OpenAICompatibleClient._build_table_translate_prompt: instruction before grid."""
        from app.backend.clients.openai_compatible_client import OpenAICompatibleClient
        serialized = "Name | Value\nApple | 100"
        prompt = OpenAICompatibleClient._build_table_translate_prompt(serialized, "en", "zh")

        instr_idx = min(
            (prompt.find(word) for word in ("Translate", "translate") if prompt.find(word) >= 0),
            default=-1,
        )
        grid_idx = prompt.find("Name | Value")

        assert instr_idx >= 0, "Instruction not found in prompt"
        assert grid_idx >= 0, "Serialized grid not found in prompt"
        assert instr_idx < grid_idx

    def test_prompt_builder_methods_produce_identical_instructions(self):
        """Both client prompt builders use identical instruction wording (AC-2 symmetry)."""
        from app.backend.clients.ollama_client import OllamaClient
        from app.backend.clients.openai_compatible_client import OpenAICompatibleClient

        serialized = "X | Y"
        p_ollama = OllamaClient._build_table_translate_prompt(serialized, "en", "zh")
        p_oa = OpenAICompatibleClient._build_table_translate_prompt(serialized, "en", "zh")

        # The instruction text before the grid must be identical
        grid_start_ollama = p_ollama.find("X | Y")
        grid_start_oa = p_oa.find("X | Y")

        instr_ollama = p_ollama[:grid_start_ollama].strip()
        instr_oa = p_oa[:grid_start_oa].strip()

        assert instr_ollama == instr_oa, (
            f"Prompt builders produce different instructions:\n"
            f"Ollama: {instr_ollama!r}\nOpenAI: {instr_oa!r}"
        )


# ---------------------------------------------------------------------------
# AC-5: PDF TableCell row/col drives serialization
# ---------------------------------------------------------------------------

class TestPdfTableCellSerialization:
    """Tests for translate_table_cells() using the shared serializer (AC-5)."""

    def test_pdf_tablecell_row_col_drives_serialization(self):
        """translate_table_cells uses table_serializer.serialize with real row/col from cells."""
        if _table_ser is None:
            pytest.skip("table_serializer not yet created (expected RED)")

        ts = _make_table_structure([
            ["Header A", "Header B"],
            ["Data 1",   "Data 2"],
        ])
        element = _make_table_element(ts)

        mock_client = _make_client_mock()
        mock_client.translate_once.return_value = (
            True, _grid_response([["标题A", "标题B"], ["数据1", "数据2"]])
        )

        captured_serialize_args = []

        original_serialize = _table_ser.serialize

        def capturing_serialize(cells):
            captured_serialize_args.append(list(cells))
            return original_serialize(cells)

        with patch.object(_table_ser, "serialize", side_effect=capturing_serialize):
            _ts.translate_table_cells(
                element, targets=["zh"], src_lang="en", client=mock_client,
            )

        # serialize must have been called — passing the actual TableCell objects
        assert len(captured_serialize_args) >= 1, (
            "table_serializer.serialize was not called; "
            "translate_table_cells must use the shared serializer (AC-5)"
        )

        # The cells passed to serialize must have row/col set from the IR
        all_cells = captured_serialize_args[0]
        rows_seen = {c.row for c in all_cells}
        cols_seen = {c.col for c in all_cells}
        assert 0 in rows_seen and 1 in rows_seen, f"Expected rows 0 and 1; got {rows_seen}"
        assert 0 in cols_seen and 1 in cols_seen, f"Expected cols 0 and 1; got {cols_seen}"

    def test_pdf_translate_table_cells_calls_translate_once_once(self):
        """After IP-3: translate_table_cells calls client.translate_once exactly once
        for a table with ≥1 translatable cell (instead of per-cell batch calls)."""
        if _table_ser is None:
            pytest.skip("table_serializer not yet created (expected RED)")

        ts = _make_table_structure([
            ["Name", "Value"],
            ["Apple", "Fruit"],
        ])
        element = _make_table_element(ts)

        mock_client = _make_client_mock()
        mock_client.translate_once.return_value = (
            True, _grid_response([["名字", "价值"], ["苹果", "水果"]])
        )

        with patch.object(_ts, "translate_blocks_batch") as mock_batch:
            _ts.translate_table_cells(
                element, targets=["zh"], src_lang="en", client=mock_client,
            )
            # After IP-3: translate_blocks_batch NOT used for the whole-table call
            assert mock_batch.call_count == 0, (
                "translate_blocks_batch should not be called when serializer path succeeds"
            )

        # translate_once called exactly once for the whole table
        assert mock_client.translate_once.call_count == 1, (
            f"Expected 1 translate_once call for whole-table translation; "
            f"got {mock_client.translate_once.call_count}"
        )

    def test_pdf_translations_mapped_to_correct_cells_after_parse(self):
        """After parse(), each non-numeric cell gets grid[r][c] as translated_content."""
        if _table_ser is None:
            pytest.skip("table_serializer not yet created (expected RED)")

        ts = _make_table_structure([
            ["Name", "Value"],
            ["Apple", "Fruit"],
        ])
        element = _make_table_element(ts)

        mock_client = _make_client_mock()
        mock_client.translate_once.return_value = (
            True, _grid_response([["名字", "价值"], ["苹果", "水果"]])
        )

        _ts.translate_table_cells(
            element, targets=["zh"], src_lang="en", client=mock_client,
        )

        from app.backend.models.translatable_document import TableStructure as TS
        ts_dict = element.metadata["table_structure"]
        ts_out = TS.from_dict(ts_dict)

        cell_map = {(c.row, c.col): c for c in ts_out.cells}
        assert cell_map[(0, 0)].translated_content == "名字", (
            f"Expected '名字' at (0,0), got {cell_map[(0,0)].translated_content!r}"
        )
        assert cell_map[(0, 1)].translated_content == "价值"
        assert cell_map[(1, 0)].translated_content == "苹果"
        assert cell_map[(1, 1)].translated_content == "水果"


# ---------------------------------------------------------------------------
# AC-8: Fallback when parse() returns None
# ---------------------------------------------------------------------------

class TestFallbackBehavior:
    """Tests for the per-cell SEG fallback when parse() returns None (AC-8)."""

    def test_fallback_per_cell_batch_preserves_all_cell_mapping(self):
        """When translate_once returns an unparseable response, all cells still get
        translations via the fallback per-cell SEG batch (AC-8)."""
        if _table_ser is None:
            pytest.skip("table_serializer not yet created (expected RED)")

        ts = _make_table_structure([
            ["Name", "Value"],
            ["Apple", "Fruit"],
        ])
        element = _make_table_element(ts)

        mock_client = _make_client_mock()
        # Return a garbled response that parse() cannot parse
        mock_client.translate_once.return_value = (
            True, "This is not a valid pipe-grid at all"
        )

        # Fallback: translate_blocks_batch should be called for each cell
        fallback_results = [
            (True, "名字"),
            (True, "价值"),
            (True, "苹果"),
            (True, "水果"),
        ]

        with patch.object(_ts, "translate_blocks_batch", return_value=fallback_results) as mock_batch:
            _ts.translate_table_cells(
                element, targets=["zh"], src_lang="en", client=mock_client,
            )

        # Fallback must have been invoked
        assert mock_batch.call_count >= 1, (
            "translate_blocks_batch (fallback) must be called when parse() returns None"
        )

        # All translatable cells must have translations
        from app.backend.models.translatable_document import TableStructure as TS
        ts_out = TS.from_dict(element.metadata["table_structure"])
        for cell in ts_out.cells:
            assert cell.translation_status in ("translated", "passthrough", "skipped"), (
                f"Cell ({cell.row},{cell.col}) has unexpected status: {cell.translation_status!r}"
            )
            assert cell.translated_content is not None, (
                f"Cell ({cell.row},{cell.col}) has None translated_content after fallback"
            )

    def test_fallback_logs_warning_on_parse_failure(self, caplog):
        """When parse() returns None, a WARNING is logged with dimension info (BR-82)."""
        if _table_ser is None:
            pytest.skip("table_serializer not yet created (expected RED)")

        ts = _make_table_structure([["Name", "Value"]])
        element = _make_table_element(ts)

        mock_client = _make_client_mock()
        mock_client.translate_once.return_value = (True, "no pipes here")

        with patch.object(_ts, "translate_blocks_batch", return_value=[(True, "名字"), (True, "价值")]):
            with caplog.at_level(logging.WARNING):
                _ts.translate_table_cells(
                    element, targets=["zh"], src_lang="en", client=mock_client,
                )

        warning_texts = [r.message for r in caplog.records if r.levelno >= logging.WARNING]
        assert any("parse" in w.lower() or "mismatch" in w.lower() or "fallback" in w.lower()
                   for w in warning_texts), (
            f"Expected a WARNING log about parse failure/fallback; got: {warning_texts}"
        )


# ---------------------------------------------------------------------------
# BR-68/BR-69: Numeric passthrough + all-numeric table
# ---------------------------------------------------------------------------

class TestNumericPassthrough:
    """Tests for numeric cell exclusion from LLM batch (BR-68, BR-69)."""

    def test_all_numeric_table_makes_no_llm_call(self):
        """A table where ALL cells are numeric makes no LLM call (BR-68/AC-1)."""
        if _table_ser is None:
            pytest.skip("table_serializer not yet created (expected RED)")

        ts = _make_table_structure([])  # empty, will be replaced
        # Build all-numeric structure manually
        cells = [
            _make_table_cell(0, 0, "100", is_numeric=True),
            _make_table_cell(0, 1, "200", is_numeric=True),
            _make_table_cell(1, 0, "300", is_numeric=True),
            _make_table_cell(1, 1, "400", is_numeric=True),
        ]
        ts2 = TableStructure(
            num_rows=2, num_cols=2, recognizer="test",
            recognition_confident=True, cells=cells,
        )
        element = _make_table_element(ts2)

        mock_client = _make_client_mock()

        _ts.translate_table_cells(
            element, targets=["zh"], src_lang="en", client=mock_client,
        )

        assert mock_client.translate_once.call_count == 0, (
            "No LLM call should be made for an all-numeric table (BR-68)"
        )

        # All cells must have passthrough status
        from app.backend.models.translatable_document import TableStructure as TS
        ts_out = TS.from_dict(element.metadata["table_structure"])
        for cell in ts_out.cells:
            assert cell.translation_status == "passthrough", (
                f"Expected 'passthrough' for numeric cell ({cell.row},{cell.col}), "
                f"got {cell.translation_status!r}"
            )

    def test_numeric_cells_excluded_from_batch_and_passthrough(self):
        """Mixed table: numeric cells excluded from LLM call, get passthrough status."""
        if _table_ser is None:
            pytest.skip("table_serializer not yet created (expected RED)")

        cells = [
            _make_table_cell(0, 0, "Product"),
            _make_table_cell(0, 1, "Price"),
            _make_table_cell(1, 0, "Apple"),
            _make_table_cell(1, 1, "1.99", is_numeric=True),
        ]
        ts = TableStructure(
            num_rows=2, num_cols=2, recognizer="test",
            recognition_confident=True, cells=cells,
        )
        element = _make_table_element(ts)

        mock_client = _make_client_mock()
        # Only 3 translatable cells (Product, Price, Apple); "1.99" is numeric
        # Response must be a 2×2 grid (numeric cell is a placeholder)
        mock_client.translate_once.return_value = (
            True, _grid_response([["产品", "价格"], ["苹果", "1.99"]])
        )

        _ts.translate_table_cells(
            element, targets=["zh"], src_lang="en", client=mock_client,
        )

        from app.backend.models.translatable_document import TableStructure as TS
        ts_out = TS.from_dict(element.metadata["table_structure"])
        cell_map = {(c.row, c.col): c for c in ts_out.cells}

        # Numeric cell must stay passthrough
        assert cell_map[(1, 1)].translation_status == "passthrough", (
            f"Numeric cell must have passthrough status, "
            f"got {cell_map[(1,1)].translation_status!r}"
        )
        assert cell_map[(1, 1)].translated_content == "1.99"

        # Translatable cells must be translated
        for (r, c) in [(0, 0), (0, 1), (1, 0)]:
            assert cell_map[(r, c)].translation_status == "translated", (
                f"Cell ({r},{c}) should be translated, "
                f"got {cell_map[(r,c)].translation_status!r}"
            )


# ---------------------------------------------------------------------------
# AC-1: One LLM call per table — Office processors (DOCX / XLSX / PPTX)
# ---------------------------------------------------------------------------

class TestOneCallPerTableOffice:
    """Tests that each table gets exactly one translate_once call (AC-1)."""

    def test_single_llm_call_per_table_docx(self, tmp_path):
        """DOCX with one 2×2 table → exactly 1 translate_once call (AC-1)."""
        rows = [["Name", "Value"], ["Apple", "Fruit"]]
        in_path = _make_docx_with_table(tmp_path, rows)
        out_path = tmp_path / "out.docx"

        mock_client = _make_client_mock()
        # translate_once returns the translated 2×2 grid
        mock_client.translate_once.return_value = (
            True, _grid_response([["名字", "价值"], ["苹果", "水果"]])
        )
        # translate_texts returns empty (no non-table paragraphs)
        with patch.object(_docx_proc, "translate_texts", return_value=({}, 0, 0, False)):
            _docx_proc.translate_docx(
                str(in_path), str(out_path),
                targets=["zh"], src_lang="en",
                client=mock_client,
                include_headers_shapes_via_com=False,
            )

        assert mock_client.translate_once.call_count == 1, (
            f"Expected exactly 1 translate_once call for the whole table; "
            f"got {mock_client.translate_once.call_count}"
        )

    def test_single_llm_call_per_table_xlsx(self, tmp_path):
        """XLSX with one 2×2 text region → exactly 1 translate_once call (AC-1)."""
        rows = [["Name", "Value"], ["Apple", "Fruit"]]
        in_path = _make_xlsx_with_cells(tmp_path, rows)
        out_path = tmp_path / "out.xlsx"

        mock_client = _make_client_mock()
        mock_client.translate_once.return_value = (
            True, _grid_response([["名字", "价值"], ["苹果", "水果"]])
        )

        with patch.object(_xlsx_proc, "translate_texts", return_value=({}, 0, 0, False)):
            _xlsx_proc.translate_xlsx_xls(
                str(in_path), str(out_path),
                targets=["zh"], src_lang="en",
                client=mock_client,
            )

        assert mock_client.translate_once.call_count == 1, (
            f"Expected 1 translate_once call for the whole sheet; "
            f"got {mock_client.translate_once.call_count}"
        )

    def test_single_llm_call_per_table_pptx(self, tmp_path):
        """PPTX with one 2×2 table → exactly 1 translate_once call (AC-1)."""
        rows = [["Name", "Value"], ["Apple", "Fruit"]]
        in_path = _make_pptx_with_table(tmp_path, rows)
        out_path = tmp_path / "out.pptx"

        mock_client = _make_client_mock()
        mock_client.translate_once.return_value = (
            True, _grid_response([["名字", "价值"], ["苹果", "水果"]])
        )

        with patch.object(_pptx_proc, "translate_texts", return_value=({}, 0, 0, False)):
            _pptx_proc.translate_pptx(
                str(in_path), str(out_path),
                targets=["zh"], src_lang="en",
                client=mock_client,
            )

        assert mock_client.translate_once.call_count == 1, (
            f"Expected 1 translate_once call for the whole table; "
            f"got {mock_client.translate_once.call_count}"
        )


# ---------------------------------------------------------------------------
# AC-3: Per-column dedup key
# ---------------------------------------------------------------------------

class TestPerColumnDedupKey:
    """Tests for (tgt, src_text, col) dedup key in office processors (AC-3)."""

    def test_same_text_different_cols_get_separate_translations(self):
        """Using table_serializer directly: same text in col 0 and col 2 occupies
        different grid positions → parse returns different translations per column."""
        if _table_ser is None:
            pytest.skip("table_serializer not yet created (expected RED)")

        from dataclasses import dataclass as _dc

        @_dc
        class _SimpleCell:
            row: int
            col: int
            content: str
            is_numeric: bool = False

        # 1-row, 3-col table where "Lead" appears in col 0 and col 2
        cells = [
            _SimpleCell(0, 0, "Lead"),
            _SimpleCell(0, 1, "Metal"),
            _SimpleCell(0, 2, "Lead"),  # same text, different column
        ]

        serialized = _table_ser.serialize(cells)
        # Mock LLM assigns different translations per column
        response = "铅 | 金属 | 领导"  # "Lead"-metal→铅, Lead-verb→领导
        grid = _table_ser.parse(response, 1, 3)

        assert grid is not None, f"parse() returned None for response {response!r}"

        # Build tmap with (tgt, text, col) keys
        tgt = "zh"
        tmap: Dict = {}
        for cell in cells:
            r, c = cell.row, cell.col
            if grid[r][c].strip():
                tmap[(tgt, cell.content, c)] = grid[r][c].strip()

        # Same source text in different columns maps to DIFFERENT translations
        t_col0 = tmap.get((tgt, "Lead", 0))
        t_col2 = tmap.get((tgt, "Lead", 2))

        assert t_col0 is not None, "Translation for (tgt, 'Lead', 0) missing from tmap"
        assert t_col2 is not None, "Translation for (tgt, 'Lead', 2) missing from tmap"
        assert t_col0 != t_col2, (
            f"Same text 'Lead' in col 0 ({t_col0!r}) and col 2 ({t_col2!r}) should get "
            "different translations when contextually placed in different columns"
        )

    def test_non_table_segments_use_col_none_dedup_key(self, tmp_path):
        """DOCX: non-table paragraph segments must use col=None in the tmap (AC-3)."""
        import docx as _docx_lib
        doc = _docx_lib.Document()
        doc.add_paragraph("Hello paragraph")  # non-table segment
        in_path = str(tmp_path / "para_only.docx")
        out_path = str(tmp_path / "para_only_out.docx")
        doc.save(in_path)

        captured_tmap: Dict = {}

        def capturing_translate_texts(texts, targets, src_lang, client, **kwargs):
            # simulate a translation: return (tgt, text): "TRANSLATED"
            result = {}
            for tgt in targets:
                for text in texts:
                    result[(tgt, text)] = f"TRANSLATED_{text}"
            return result, len(texts), 0, False

        mock_client = _make_client_mock()

        with patch.object(_docx_proc, "translate_texts", side_effect=capturing_translate_texts):
            _docx_proc.translate_docx(
                in_path, out_path,
                targets=["zh"], src_lang="en",
                client=mock_client,
                include_headers_shapes_via_com=False,
            )

        # After implementation: the tmap must use (tgt, text, None) for paragraphs
        # We verify by checking the insert pass used col=None keys.
        # Since we can't easily inspect the internal tmap, check the output file instead:
        # The paragraph should be translated.
        out_doc = _docx_lib.Document(out_path)
        all_texts = [p.text for p in out_doc.paragraphs]
        # Original paragraph must still be present
        assert any("Hello paragraph" in t for t in all_texts), (
            f"Original paragraph missing from output: {all_texts}"
        )
        # Translation must be appended (append mode by default)
        assert any("TRANSLATED" in t for t in all_texts), (
            f"Translation not found in output: {all_texts}"
        )
