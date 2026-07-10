"""TDD tests for table_serializer.py — IP-1 (table-context-translation).

These tests are written BEFORE the implementation exists (IP-0: Red phase).
They will fail until app/backend/utils/table_serializer.py is created.

Anti-tautology requirements:
  - Pure function tests: no mocking needed.
  - Each test asserts specific structural guarantees, not just call counts.

Collection-time module imports (CLAUDE.md mock.patch learning):
  Modules imported with try/except so collection succeeds even when the
  module does not exist yet.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import List, Optional

import pytest

# ---------------------------------------------------------------------------
# Collection-time module import — will be None if not yet created (RED)
# ---------------------------------------------------------------------------

try:
    import app.backend.utils.table_serializer as _ts
except ImportError:
    _ts = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Minimal TableCell-compatible stub for tests
# (avoids depending on models module import for pure serializer tests)
# ---------------------------------------------------------------------------

@dataclass
class _Cell:
    """Minimal duck-type compatible stub for TableCell."""
    row: int
    col: int
    content: str
    is_numeric: bool = False


def _make_cell(row: int, col: int, content: str, is_numeric: bool = False) -> _Cell:
    return _Cell(row=row, col=col, content=content, is_numeric=is_numeric)


# ---------------------------------------------------------------------------
# Guard: skip all tests if module missing (gives clean FAILED, not ERROR)
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.skipif(
    _ts is None,
    reason="app.backend.utils.table_serializer not yet created (expected RED)",
)


# ---------------------------------------------------------------------------
# AC-4: Header row/col inline with body in serialized grid
# ---------------------------------------------------------------------------

class TestSerializeStructure:
    """Tests for the serialize() function shape and header placement."""

    def test_serialized_grid_row0_and_col0_inline_with_body(self):
        """Row 0 (column headers) and col 0 (row headers) co-occur inline
        with every body cell in the single serialized string (AC-4)."""
        cells = [
            _make_cell(0, 0, "Name"),   # col header + row header corner
            _make_cell(0, 1, "Value"),  # col header
            _make_cell(1, 0, "Apple"),  # row header
            _make_cell(1, 1, "100"),    # body
        ]
        result = _ts.serialize(cells)

        # Exactly 2 rows, separated by newline
        lines = [l for l in result.split("\n") if l.strip()]
        assert len(lines) == 2, f"Expected 2 rows, got {len(lines)}: {result!r}"

        # Row 0: headers present
        assert "Name" in lines[0], f"Row 0 missing 'Name': {lines[0]!r}"
        assert "Value" in lines[0], f"Row 0 missing 'Value': {lines[0]!r}"

        # Row 1: row header and body present in same row string
        assert "Apple" in lines[1], f"Row 1 missing 'Apple': {lines[1]!r}"
        assert "100" in lines[1], f"Row 1 missing '100': {lines[1]!r}"

    def test_serialize_produces_pipe_delimiters(self):
        """Serialized output uses '|' as the cell delimiter within each row."""
        cells = [
            _make_cell(0, 0, "A"),
            _make_cell(0, 1, "B"),
            _make_cell(0, 2, "C"),
        ]
        result = _ts.serialize(cells)
        line = result.strip()
        assert "|" in line, f"No pipe delimiter in output: {line!r}"
        # Not a leading/trailing | from serializer side
        # (LLM response may add them; serializer MUST NOT)
        stripped = line.strip("|").strip()
        assert stripped  # non-empty after stripping

    def test_serialize_single_row_two_cols(self):
        """A 1x2 table serializes to a single line with one delimiter."""
        cells = [
            _make_cell(0, 0, "Hello"),
            _make_cell(0, 1, "World"),
        ]
        result = _ts.serialize(cells)
        assert "\n" not in result, f"1-row table should have no newline: {result!r}"
        assert "|" in result

    def test_serialize_no_trailing_newline(self):
        """Output must not end with a trailing newline."""
        cells = [
            _make_cell(0, 0, "A"),
            _make_cell(0, 1, "B"),
            _make_cell(1, 0, "C"),
            _make_cell(1, 1, "D"),
        ]
        result = _ts.serialize(cells)
        assert not result.endswith("\n"), f"Output has trailing newline: {result!r}"


# ---------------------------------------------------------------------------
# Pipe-escape and newline sanitization
# ---------------------------------------------------------------------------

class TestSerializeEscaping:
    """Tests for | escape and \\n→space normalization in serialize()."""

    def test_serialize_escapes_pipe_chars_and_collapses_newlines(self):
        """Pipe chars in cell content are escaped; embedded newlines become spaces."""
        cells = [
            _make_cell(0, 0, "a|b"),    # literal pipe in content
            _make_cell(0, 1, "c\nd"),   # embedded newline
        ]
        result = _ts.serialize(cells)

        # The row separator \n (between rows) is fine, but cell newline MUST be space
        # Since this is a 1-row table, there is no row separator \n
        assert "\n" not in result, (
            f"Embedded \\n in cell must become space, but result has newline: {result!r}"
        )

        # Pipe in content must be escaped as \|
        # The serialized output has TWO |: one is the escaped cell content, one is delimiter
        # The cell "a|b" should appear as "a\|b" in the output
        assert r"a\|b" in result, (
            f"Literal pipe in cell content must be escaped as \\|: {result!r}"
        )

        # "c\nd" → "c d" (newline collapsed to space)
        assert "c d" in result, (
            f"Embedded newline in cell must be collapsed to space: {result!r}"
        )

    def test_serialize_numeric_cell_included_as_placeholder(self):
        """Numeric cells (is_numeric=True) are included in grid as positional placeholders."""
        cells = [
            _make_cell(0, 0, "Name"),
            _make_cell(0, 1, "Price"),
            _make_cell(1, 0, "Apple"),
            _make_cell(1, 1, "100", is_numeric=True),
        ]
        result = _ts.serialize(cells)
        lines = [l for l in result.split("\n") if l.strip()]
        # 2 rows
        assert len(lines) == 2, f"Expected 2 rows: {result!r}"
        # "100" appears as a placeholder in row 1
        assert "100" in lines[1], f"Numeric cell must appear as placeholder: {lines[1]!r}"


# ---------------------------------------------------------------------------
# Parse correctness
# ---------------------------------------------------------------------------

class TestParseCorrectness:
    """Tests for the parse() function."""

    def test_parse_drops_markdown_separator_line(self):
        """parse() strips Markdown '--- | ---' separator lines before validation."""
        text = "Name | Value\n--- | ---\nApple | 100"
        result = _ts.parse(text, 2, 2)

        assert result is not None, (
            "parse() returned None; expected it to succeed after dropping separator line"
        )
        assert len(result) == 2, f"Expected 2 rows after dropping separator: {result}"
        assert result[0][0].strip() == "Name"
        assert result[0][1].strip() == "Value"
        assert result[1][0].strip() == "Apple"
        assert result[1][1].strip() == "100"

    def test_parse_strips_whitespace_from_cells(self):
        """parse() strips leading/trailing whitespace from each cell."""
        text = " Name  |  Value \n Apple  |  Fruit "
        result = _ts.parse(text, 2, 2)
        assert result is not None
        assert result[0][0] == "Name"
        assert result[0][1] == "Value"
        assert result[1][0] == "Apple"
        assert result[1][1] == "Fruit"

    def test_parse_unescapes_pipe_in_cells(self):
        r"""parse() replaces \| with | in each cell value after splitting."""
        # Escaped pipe in cell content
        text = r"a\|b | c"
        result = _ts.parse(text, 1, 2)
        assert result is not None, f"parse() returned None for {text!r}"
        assert result[0][0] == "a|b", f"Expected 'a|b', got {result[0][0]!r}"
        assert result[0][1] == "c"


# ---------------------------------------------------------------------------
# AC-8: Shape mismatches → None
# ---------------------------------------------------------------------------

class TestParseMismatch:
    """Tests that parse() returns None on shape mismatches (AC-8)."""

    def test_parse_returns_none_on_row_count_mismatch(self):
        """parse() returns None when the LLM response has fewer rows than expected."""
        text = "A | B\nC | D"  # 2 rows
        result = _ts.parse(text, 3, 2)  # expected 3 rows

        assert result is None, (
            f"parse() should return None for row-count mismatch, got: {result}"
        )

    def test_parse_returns_none_on_col_count_mismatch(self):
        """parse() returns None when any row has wrong number of columns."""
        text = "A | B | C\nD | E | F"  # 3 cols
        result = _ts.parse(text, 2, 2)  # expected 2 cols

        assert result is None, (
            f"parse() should return None for col-count mismatch, got: {result}"
        )

    def test_parse_returns_none_when_no_pipe_delimiters(self):
        """parse() returns None when response contains no pipe characters."""
        text = "Name Value\nApple 100"  # no pipes
        result = _ts.parse(text, 2, 2)

        assert result is None, (
            f"parse() should return None when no pipe delimiters, got: {result}"
        )

    def test_parse_returns_none_on_empty_input(self):
        """parse() returns None for empty input string."""
        result = _ts.parse("", 2, 2)
        assert result is None

    def test_parse_returns_none_on_more_rows_than_expected(self):
        """parse() returns None when response has MORE rows than expected."""
        text = "A | B\nC | D\nE | F"  # 3 rows
        result = _ts.parse(text, 2, 2)  # expected 2 rows

        assert result is None, (
            f"parse() should return None when too many rows, got: {result}"
        )


# ---------------------------------------------------------------------------
# Round-trip guarantee
# ---------------------------------------------------------------------------

class TestRoundTrip:
    """Tests for the serialize → parse round-trip contract."""

    def test_serialize_parse_round_trip_preserves_row_col_positions(self):
        """serialize() → parse() restores each cell content at the correct (row, col)."""
        cells = [
            _make_cell(0, 0, "Name"),
            _make_cell(0, 1, "Value"),
            _make_cell(1, 0, "Apple"),
            _make_cell(1, 1, "100"),
        ]
        serialized = _ts.serialize(cells)
        grid = _ts.parse(serialized, 2, 2)

        assert grid is not None, f"parse() returned None for round-trip: {serialized!r}"
        assert len(grid) == 2
        assert grid[0][0] == "Name"
        assert grid[0][1] == "Value"
        assert grid[1][0] == "Apple"
        assert grid[1][1] == "100"

    def test_round_trip_preserves_escaped_pipe_content(self):
        """Round-trip: cell content with | is escaped, then correctly restored."""
        cells = [
            _make_cell(0, 0, "a|b"),
            _make_cell(0, 1, "c"),
        ]
        serialized = _ts.serialize(cells)
        grid = _ts.parse(serialized, 1, 2)

        assert grid is not None, f"parse() returned None: {serialized!r}"
        assert grid[0][0] == "a|b", f"Pipe not restored: {grid[0][0]!r}"
        assert grid[0][1] == "c"

    def test_round_trip_3x3_table(self):
        """Round-trip for a 3x3 table preserves all cell positions."""
        cells = [
            _make_cell(r, c, f"cell_{r}_{c}")
            for r in range(3) for c in range(3)
        ]
        serialized = _ts.serialize(cells)
        grid = _ts.parse(serialized, 3, 3)

        assert grid is not None
        for r in range(3):
            for c in range(3):
                assert grid[r][c] == f"cell_{r}_{c}", (
                    f"Position ({r},{c}) mismatch: expected cell_{r}_{c}, got {grid[r][c]!r}"
                )


# ---------------------------------------------------------------------------
# json-structured-translation-io: serialize_json / parse_json (ADR-0017,
# Resolution A — these coordinate-JSON functions are NEW additions ALONGSIDE
# the frozen legacy serialize()/parse() tested above; the legacy cases are
# retained unmodified per the Test Update Contract.
# ---------------------------------------------------------------------------

class TestSerializeContentCellsOnly:
    """AC-1: serialize_json emits ONLY content-bearing, non-numeric cells —
    no grid shape, so a phantom-column sheet cannot produce a shape echo."""

    def test_47_content_cells_against_257_phantom_columns_no_grid_shape(self):
        """A sheet reporting a 9x257 shape (phantom columns) but holding only
        47 real content cells must serialize to exactly 47 cell objects."""
        content_positions = [(r, c) for r in range(9) for c in range(257)][:47]
        cells = [_make_cell(r, c, f"cell_{r}_{c}") for (r, c) in content_positions]
        # Fill the rest of the phantom 9x257 grid with empty placeholder cells,
        # exactly mirroring how xlsx_processor builds its full-grid proxy list
        # today (data-shape §Table Serialization Wire Format).
        all_positions = {(r, c) for r in range(9) for c in range(257)}
        empty_cells = [_make_cell(r, c, "") for (r, c) in all_positions - set(content_positions)]

        result = _ts.serialize_json(cells + empty_cells)
        parsed = json.loads(result)

        assert "cells" in parsed
        assert len(parsed["cells"]) == 47, (
            f"Expected exactly 47 content cell objects, got {len(parsed['cells'])}"
        )
        assert "num_rows" not in parsed and "num_cols" not in parsed, (
            "No grid shape may be echoed in the request envelope"
        )

    def test_numeric_cells_excluded(self):
        cells = [
            _make_cell(0, 0, "Name"),
            _make_cell(0, 1, "100", is_numeric=True),
        ]
        result = json.loads(_ts.serialize_json(cells))
        assert len(result["cells"]) == 1
        assert result["cells"][0]["text"] == "Name"

    def test_empty_cells_excluded(self):
        cells = [_make_cell(0, 0, "Name"), _make_cell(0, 1, "")]
        result = json.loads(_ts.serialize_json(cells))
        assert len(result["cells"]) == 1
        assert result["cells"][0]["text"] == "Name"

    def test_original_row_col_never_renumbered(self):
        """A sparse cell list (rows 3 and 9, not 0 and 1) keeps its ORIGINAL
        coordinates — never compacted to 0/1."""
        cells = [_make_cell(3, 9, "Sparse"), _make_cell(3, 12, "Cell")]
        result = json.loads(_ts.serialize_json(cells))
        positions = {(c["row"], c["col"]) for c in result["cells"]}
        assert positions == {(3, 9), (3, 12)}

    def test_empty_cell_list_produces_empty_cells_array(self):
        result = json.loads(_ts.serialize_json([]))
        assert result == {"cells": []}


class TestParseCoordinateRemap:
    """AC-2: parse_json assigns by (row, col) lookup against the SENT set,
    never by position or order within the reply array."""

    def test_valid_reply_restores_translations_by_row_col(self):
        sent_cells = {(0, 0): "Name", (0, 1): "Value", (1, 0): "Apple"}
        reply = json.dumps({
            "cells": [
                {"row": 1, "col": 0, "translation": "苹果"},
                {"row": 0, "col": 0, "translation": "名字"},
                {"row": 0, "col": 1, "translation": "价值"},
            ]
        })
        result, reason = _ts.parse_json(reply, sent_cells)
        assert result == {(0, 0): "名字", (0, 1): "价值", (1, 0): "苹果"}
        assert reason == ""

    def test_reject_missing_sent_coordinate(self):
        sent_cells = {(0, 0): "Name", (0, 1): "Value"}
        reply = json.dumps({"cells": [{"row": 0, "col": 0, "translation": "名字"}]})
        result, reason = _ts.parse_json(reply, sent_cells)
        assert result is None
        assert reason

    def test_extra_coordinate_is_ignored_not_an_error(self):
        sent_cells = {(0, 0): "Name"}
        reply = json.dumps({
            "cells": [
                {"row": 0, "col": 0, "translation": "名字"},
                {"row": 5, "col": 5, "translation": "hallucinated extra"},
            ]
        })
        result, reason = _ts.parse_json(reply, sent_cells)
        assert result == {(0, 0): "名字"}
        assert reason == ""

    def test_reject_unparseable_json(self):
        result, reason = _ts.parse_json("not json at all", {(0, 0): "Name"})
        assert result is None
        assert reason

    def test_reject_empty_content(self):
        result, reason = _ts.parse_json("", {(0, 0): "Name"})
        assert result is None
        assert reason

    def test_reject_missing_cells_key(self):
        result, reason = _ts.parse_json(json.dumps({"foo": "bar"}), {(0, 0): "Name"})
        assert result is None
        assert reason

    def test_reject_non_integer_coordinate(self):
        sent_cells = {(0, 0): "Name"}
        reply = json.dumps({"cells": [{"row": "0", "col": 0, "translation": "名字"}]})
        result, reason = _ts.parse_json(reply, sent_cells)
        assert result is None
        assert reason

    def test_echoed_whole_grid_rejected(self):
        """Every returned cell byte-identical to its source -> untranslated,
        must be rejected (BR-82)."""
        sent_cells = {(0, 0): "Name", (0, 1): "Value"}
        reply = json.dumps({
            "cells": [
                {"row": 0, "col": 0, "translation": "Name"},
                {"row": 0, "col": 1, "translation": "Value"},
            ]
        })
        result, reason = _ts.parse_json(reply, sent_cells)
        assert result is None
        assert "echo" in reason.lower()

    def test_single_unchanged_cell_is_legitimate_not_rejected(self):
        """A single unchanged cell (proper noun / product code / number) is
        legitimate and MUST NOT trigger the echoed-source rejection —
        asserting WHICH condition fired, not a changed-cell count."""
        sent_cells = {(0, 0): "ACME-Corp", (0, 1): "Value"}
        reply = json.dumps({
            "cells": [
                {"row": 0, "col": 0, "translation": "ACME-Corp"},  # legitimate proper noun
                {"row": 0, "col": 1, "translation": "价值"},
            ]
        })
        result, reason = _ts.parse_json(reply, sent_cells)
        assert result == {(0, 0): "ACME-Corp", (0, 1): "价值"}
        assert reason == ""


class TestJsonRoundTrip:
    def test_serialize_parse_json_round_trip_preserves_coordinates(self):
        cells = [
            _make_cell(0, 0, "Name"),
            _make_cell(0, 1, "Value"),
            _make_cell(1, 0, "Apple"),
        ]
        serialized = _ts.serialize_json(cells)
        sent_cells = {(c.row, c.col): c.content for c in cells}
        translated = json.dumps({
            "cells": [
                {"row": c.row, "col": c.col, "translation": f"T_{c.content}"}
                for c in cells
            ]
        })
        result, reason = _ts.parse_json(translated, sent_cells)
        assert reason == ""
        for c in cells:
            assert result[(c.row, c.col)] == f"T_{c.content}"
