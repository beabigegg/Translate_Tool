"""Shared table serialization utility (table-context-translation).

Converts a recognized table's cells to/from a Markdown pipe-grid string for
whole-table LLM translation. This is the single source of truth for the
wire format used by both Ollama and OpenAI-compatible clients, and the PDF
translation_service cell-batch path.

See contracts/data/data-shape-contract.md §Table Serialization Wire Format.
"""

from __future__ import annotations

import re
from typing import Any, List, Optional


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
