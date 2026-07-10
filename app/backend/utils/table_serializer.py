"""Shared table serialization utility (table-context-translation;
json-structured-translation-io, ADR-0017).

Two wire formats coexist here, gated by `config.JSON_STRUCTURED_TRANSLATION_ENABLED`
(Resolution A, see specs/changes/json-structured-translation-io/implementation-plan.md):

- ``serialize()`` / ``parse()``: the legacy Markdown pipe-grid, positional and
  shape-counted. RETAINED and FROZEN — reachable only when the flag is false.
  No new caller may use these two functions.
- ``serialize_json()`` / ``parse_json()``: the coordinate-carrying JSON cell
  list (BR-79, BR-82, BR-83) that replaces the pipe-grid on the flag-ON path.
  Sends only content-bearing, non-numeric cells at their ORIGINAL `(row, col)`
  coordinate — no grid shape is echoed, so the phantom-column defect (a sheet
  reporting a 9x257 shape when only 47 cells hold content) cannot recur.

See contracts/data/data-shape-contract.md §Table Serialization Wire Format
(normative for both the request/response envelope and the reject/tolerate
rules of the JSON path).
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple


def serialize(cells: Any) -> str:
    """Serialize a list of table cells to a Markdown pipe-grid string.

    Each cell must have ``row``, ``col``, ``content``, and ``is_numeric``
    attributes (duck-typed; accepts TableCell IR objects or compatible stubs).

    Serialization rules (normative, per data-shape-contract.md):
    - Rows separated by ``\\n``; no trailing newline.
    - Cells within a row separated by `` | `` (space-pipe-space).
    - No leading or trailing ``|`` on any row.
    - Literal ``|`` in cell content escaped as ``\\|``.
    - Embedded ``\\n`` in cell content replaced by a single space.
    - Numeric (is_numeric=True) and empty cells included as positional
      placeholders (grid shape preserved for parse() round-trip).

    Args:
        cells: Iterable of cell objects with row/col/content/is_numeric attrs.

    Returns:
        Markdown pipe-grid string.  Empty string when cells is empty.
    """
    cells_list = list(cells)
    if not cells_list:
        return ""

    num_rows = max(c.row for c in cells_list) + 1
    num_cols = max(c.col for c in cells_list) + 1

    # Build grid filled with empty strings
    grid: List[List[str]] = [["" for _ in range(num_cols)] for _ in range(num_rows)]

    for cell in cells_list:
        content = cell.content or ""
        # Escape literal | → \|
        content = content.replace("|", r"\|")
        # Collapse embedded newlines → space
        content = content.replace("\n", " ")
        grid[cell.row][cell.col] = content

    # Join rows
    row_strings = [" | ".join(row) for row in grid]
    return "\n".join(row_strings)


def parse(text: str, num_rows: int, num_cols: int) -> Optional[List[List[str]]]:
    """Parse an LLM pipe-grid response into a list-of-lists grid.

    Parse rules (normative, per data-shape-contract.md):
    - Drop lines that are Markdown header-separator (consist only of ``-``,
      ``|``, ``:``, and spaces, and contain at least one ``-``).
    - Keep only lines that contain at least one ``|``.
    - Accept iff ``len(pipe_lines) == num_rows`` AND every row has
      exactly ``num_cols`` cells after splitting on unescaped ``|``.
    - After splitting, unescape ``\\|`` → ``|`` in each cell value.
    - Strip leading/trailing whitespace from each cell value.
    - Return ``None`` on any shape mismatch.

    Args:
        text: Raw LLM response string.
        num_rows: Expected number of data rows.
        num_cols: Expected number of columns per row.

    Returns:
        ``list[list[str]]`` grid on success; ``None`` on shape mismatch.
    """
    if not text:
        return None

    lines = text.split("\n")

    # Drop Markdown separator lines (e.g., "--- | ---", "---|---")
    data_lines: List[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and re.match(r'^[|\-:\s]+$', stripped) and '-' in stripped:
            # This is a separator line — skip it
            continue
        data_lines.append(line)

    # Keep only lines containing at least one |
    pipe_lines = [l for l in data_lines if "|" in l]

    if len(pipe_lines) != num_rows:
        return None

    grid: List[List[str]] = []
    for line in pipe_lines:
        # Split on unescaped | (not preceded by \)
        raw_cells = re.split(r'(?<!\\)\|', line)
        # Unescape \| → | and strip whitespace
        cells = [c.replace(r'\|', '|').strip() for c in raw_cells]
        if len(cells) != num_cols:
            return None
        grid.append(cells)

    return grid


# ---------------------------------------------------------------------------
# JSON coordinate wire format (json-structured-translation-io, BR-79/BR-82/BR-83)
# ---------------------------------------------------------------------------

def serialize_json(cells: Any) -> str:
    """Serialize a list of table cells to the coordinate JSON request envelope.

    Per data-shape-contract.md §Table Serialization Wire Format: only
    content-bearing (``content != ""``), non-numeric (``is_numeric=False``)
    cells are included, each carrying its ORIGINAL ``(row, col)`` coordinate.
    Numeric and empty cells are excluded defensively even if the caller failed
    to partition them out first (BR-68/BR-79) — never included as
    placeholders, at any position. No grid shape (``num_rows``/``num_cols``)
    is emitted.

    Args:
        cells: Iterable of cell objects with row/col/content/is_numeric attrs.

    Returns:
        JSON string: ``{"cells": [{"row": R, "col": C, "text": T}, ...]}``.
        ``cells`` is ``[]`` when no cell qualifies.
    """
    items = []
    for cell in cells:
        content = cell.content or ""
        if not content:
            continue
        if getattr(cell, "is_numeric", False):
            continue
        items.append({"row": cell.row, "col": cell.col, "text": content})
    return json.dumps({"cells": items}, ensure_ascii=False)


def parse_json(
    content: str, sent_cells: Dict[Tuple[int, int], str]
) -> Tuple[Optional[Dict[Tuple[int, int], str]], str]:
    """Parse and validate an LLM JSON table reply against the sent coordinates.

    Per data-shape-contract.md §Table Serialization Wire Format:

    - Coordinate remap: assignment is by ``(row, col)`` lookup, never by
      position or order within the array.
    - Reject — missing coordinate: if any coordinate in ``sent_cells`` has no
      matching reply entry, the WHOLE reply is rejected (never partially
      assigned).
    - Reject — malformed: unparseable JSON, empty content, a missing/non-list
      ``cells`` key, or any cell object lacking ``row``/``col``/``translation``
      or carrying a non-integer coordinate.
    - Tolerated — extra coordinates: a reply entry whose ``(row, col)`` was
      never sent is ignored, not an error.
    - Echoed-source rejection: a reply in which EVERY sent coordinate's
      translation is byte-identical to its source is untranslated and MUST be
      rejected. A single unchanged cell (proper noun, number, product code)
      is legitimate and MUST NOT trigger this.

    Args:
        content: Raw LLM reply string.
        sent_cells: Mapping of every ``(row, col)`` coordinate that was sent
            to its source text, for the echoed-source check.

    Returns:
        ``(translations, "")`` on success — a dict of every sent ``(row,
        col)`` -> its reply translation (extras dropped). ``(None, reason)``
        on any reject condition above.
    """
    if not content:
        return None, "empty content"
    try:
        data = json.loads(content)
    except (ValueError, TypeError):
        return None, "unparseable JSON"
    if not isinstance(data, dict):
        return None, "reply is not a JSON object"

    reply_cells = data.get("cells")
    if not isinstance(reply_cells, list):
        return None, "missing or non-list 'cells' key"

    reply_map: Dict[Tuple[int, int], str] = {}
    for item in reply_cells:
        if not isinstance(item, dict):
            return None, "malformed cell entry (not an object)"
        row = item.get("row")
        col = item.get("col")
        translation = item.get("translation")
        if isinstance(row, bool) or isinstance(col, bool) or not isinstance(row, int) or not isinstance(col, int):
            return None, "cell entry has a non-integer row/col coordinate"
        if not isinstance(translation, str):
            return None, "cell entry missing or non-string 'translation'"
        reply_map[(row, col)] = translation

    missing = [pos for pos in sent_cells if pos not in reply_map]
    if missing:
        return None, f"reply omits {len(missing)} sent coordinate(s): {missing[:3]}"

    if sent_cells and all(reply_map[pos] == sent_cells[pos] for pos in sent_cells):
        return None, "echoed source (whole-grid unchanged, untranslated reply)"

    return {pos: reply_map[pos] for pos in sent_cells}, ""
