"""Pure document chunking module (p2-long-doc-chunking).

No LLM client, no I/O, no database access.
Implements BR-47 through BR-53, Table O, and the data-shape §Chunk Representation
and §Reassembly contract.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from app.backend.models.translatable_document import (
    ElementType,
    TranslatableDocument,
    TranslatableElement,
)

# ---------------------------------------------------------------------------
# Token estimation heuristic (Decision 2 / design.md)
# ---------------------------------------------------------------------------

# Same chars/token divisor used in orchestrator._cap_terms_by_budget and
# config.py DEFAULT_MAX_BATCH_CHARS. Named constant for tunability.
_CHARS_PER_TOKEN: float = 2.5


def estimate_tokens(text: str) -> int:
    """Estimate token count using a character-ratio heuristic.

    Uses the same divisor (2.5 chars/token) as the rest of the codebase.
    Returns 0 for empty/null input.
    """
    if not text:
        return 0
    return max(1, int(len(text) / _CHARS_PER_TOKEN))


# ---------------------------------------------------------------------------
# ChunkRecord
# ---------------------------------------------------------------------------

@dataclass
class ChunkRecord:
    """In-memory record of a document chunk.

    Fields per data-shape §Chunk Representation:
    - chunk_index: 0-based, determines reassembly order.
    - token_span: (start, end) token positions (inclusive-exclusive) in source sequence.
    - elements: references to the same TranslatableElement objects as the parent document
                (no deep-copy, per contract).
    - overlap_tokens: tokens at the start of this chunk shared with the previous chunk's tail;
                      always 0 for chunk_index == 0 (BR-47).
    - overlap_element_count: number of leading elements that are overlap (for reassembly drop,
                             per data-shape §Reassembly contract). Not serialized.
    """

    chunk_index: int
    token_span: Tuple[int, int]
    elements: List[TranslatableElement]
    overlap_tokens: int
    overlap_element_count: int = 0


# ---------------------------------------------------------------------------
# Sentence boundary detection within a single element's text
# ---------------------------------------------------------------------------

_SENTENCE_END_RE = re.compile(r"[.!?](?:\s|$)")


def _has_sentence_boundary(text: str) -> bool:
    """Return True if text has a sentence-ending punctuation mark followed by whitespace/end."""
    return bool(_SENTENCE_END_RE.search(text))


# ---------------------------------------------------------------------------
# Boundary priority classification (BR-50)
# ---------------------------------------------------------------------------

_PARA_BREAK_TYPES = frozenset({ElementType.TEXT})
_HEADING_TYPES = frozenset({ElementType.TITLE})


def _is_structured_table(element: TranslatableElement) -> bool:
    """Return True when element is a table-typed element with a recognized TableStructure (D5).

    Such elements are atomic chunk units — they must never be a mid-element split
    target and must be treated as oversized (BR-48 own-chunk path) when they alone
    exceed num_ctx.  The chunker MUST NOT cut between them and adjacent elements using
    the normal boundary search.
    """
    return (
        element.element_type == ElementType.TABLE
        and element.metadata.get("table_structure") is not None
    )


def _boundary_priority_at(elements: List[TranslatableElement], split_idx: int) -> int:
    """Return boundary priority at position split_idx (split between [split_idx-1] and [split_idx]).

    Priority (BR-50):
      3 = paragraph break (boundary between two text-type elements)
      2 = title/heading element starts at split_idx
      1 = sentence boundary in the element at split_idx-1
      0 = no semantic boundary
    """
    if split_idx <= 0 or split_idx >= len(elements):
        return 0

    prev = elements[split_idx - 1]
    curr = elements[split_idx]

    if prev.element_type in _PARA_BREAK_TYPES and curr.element_type in _PARA_BREAK_TYPES:
        return 3
    if curr.element_type in _HEADING_TYPES:
        return 2
    if prev.element_type in _HEADING_TYPES:
        return 2
    if _has_sentence_boundary(prev.content):
        return 1
    return 0


# ---------------------------------------------------------------------------
# Overlap tail builder (BR-47)
# ---------------------------------------------------------------------------

def _build_overlap_tail(
    elements: List[TranslatableElement],
    overlap_tokens: int,
) -> Tuple[List[TranslatableElement], int]:
    """Return the minimal suffix of elements whose combined token span >= overlap_tokens.

    The tail is taken from the END of elements so it serves as the contextual
    head of the next chunk (BR-47).
    """
    if not elements or overlap_tokens <= 0:
        return [], 0

    acc = 0
    tail: List[TranslatableElement] = []
    for elem in reversed(elements):
        acc += estimate_tokens(elem.content)
        tail.insert(0, elem)
        if acc >= overlap_tokens:
            break

    return tail, acc


# ---------------------------------------------------------------------------
# Core splitter (BR-47, BR-48, BR-49, BR-50, BR-52)
# ---------------------------------------------------------------------------

def split_document(
    doc: TranslatableDocument,
    num_ctx: int,
    overlap_tokens: int,
) -> List[ChunkRecord]:
    """Split a TranslatableDocument into ChunkRecords.

    Args:
        doc: Parsed document whose elements will be chunked.
        num_ctx: Maximum token ceiling per chunk (BR-49).
        overlap_tokens: Tokens of tail-of-chunk-N duplicated as head-of-chunk-N+1 (BR-47).

    Returns:
        Ordered list of ChunkRecord instances.

    Raises:
        ValueError: When overlap_tokens >= num_ctx (BR-47, BR-49).
    """
    if overlap_tokens >= num_ctx:
        raise ValueError(
            f"overlap_tokens ({overlap_tokens}) must be less than num_ctx ({num_ctx}). "
            "Reduce CHUNK_OVERLAP_TOKENS or increase num_ctx."
        )

    elements = doc.elements

    # Edge case: empty document (data-shape §Invalid-data-behavior)
    if not elements:
        return []

    # Compute per-element token estimates
    elem_tokens: List[int] = [estimate_tokens(e.content) for e in elements]
    total_tokens = sum(elem_tokens)

    # BR-52: single-chunk optimization — no split, no overlap, no reassembly
    if total_tokens <= num_ctx:
        return [
            ChunkRecord(
                chunk_index=0,
                token_span=(0, total_tokens),
                elements=list(elements),
                overlap_tokens=0,
                overlap_element_count=0,
            )
        ]

    # -----------------------------------------------------------------------
    # Multi-chunk greedy packing
    # -----------------------------------------------------------------------
    # Effective content budget: leave room for overlap prefix on future chunks
    # (we don't reduce the budget for the first chunk since it has no overlap)
    # Strategy: greedily fill a chunk up to num_ctx tokens, then look backward
    # for the best semantic boundary to actually cut at (BR-50). The overlap
    # tail from the previous chunk is prepended to each new chunk.

    chunks: List[ChunkRecord] = []

    # new_start: index into `elements` of the first *new* (non-overlap) element
    # for the upcoming chunk.
    new_start: int = 0
    chunk_index: int = 0
    # Overlap carried forward from the previous chunk
    overlap_elems: List[TranslatableElement] = []
    overlap_tok: int = 0
    # Running token offset (for token_span accounting)
    global_token_offset: int = 0  # tokens consumed by all *new* elements emitted so far

    # Guard against infinite loops
    max_chunks = len(elements) * 2 + 2

    while new_start < len(elements):
        # Build candidate chunk: overlap prefix + as many new elements as fit
        overlap_count = len(overlap_elems)
        chunk_elems: List[TranslatableElement] = list(overlap_elems)
        chunk_tok: int = overlap_tok

        # Fill new elements until we exceed num_ctx
        read_idx = new_start
        while read_idx < len(elements):
            et = elem_tokens[read_idx]
            # BR-48: if chunk_elems is empty (e.g. overlap got trimmed), always add at
            # least one element even if it alone exceeds num_ctx
            if not chunk_elems:
                chunk_elems.append(elements[read_idx])
                chunk_tok += et
                read_idx += 1
                break  # oversized atomic element → emit immediately
            if chunk_tok + et > num_ctx:
                break  # adding this element would bust the ceiling
            chunk_elems.append(elements[read_idx])
            chunk_tok += et
            read_idx += 1

        # read_idx now points to the first element that did NOT fit.
        # If we consumed all remaining elements, just emit the chunk as-is.
        if read_idx >= len(elements):
            new_elems_in_chunk = chunk_elems[overlap_count:]
            new_tok = sum(elem_tokens[new_start + i] for i in range(len(new_elems_in_chunk)))
            chunks.append(ChunkRecord(
                chunk_index=chunk_index,
                token_span=(global_token_offset, global_token_offset + new_tok),
                elements=chunk_elems,
                overlap_tokens=overlap_tok if chunk_index > 0 else 0,
                overlap_element_count=overlap_count,
            ))
            new_start += len(new_elems_in_chunk)
            global_token_offset += new_tok
            break

        # We stopped because an element didn't fit. Find the best semantic
        # split boundary within the chunk's non-overlap portion (BR-50).
        # `chunk_elems[overlap_count:]` is the list of new elements packed so far.
        new_in_chunk = chunk_elems[overlap_count:]

        if not new_in_chunk:
            # Pathological: overlap alone fills num_ctx. Trim overlap to fit at
            # least one new element.
            et_next = elem_tokens[read_idx]
            # Use only as many overlap elements as leave room for one new element
            trimmed: List[TranslatableElement] = []
            trimmed_tok = 0
            for ov in overlap_elems:
                if trimmed_tok + estimate_tokens(ov.content) + et_next <= num_ctx:
                    trimmed.append(ov)
                    trimmed_tok += estimate_tokens(ov.content)
                else:
                    break
            overlap_elems = trimmed
            overlap_tok = trimmed_tok
            overlap_count = len(overlap_elems)
            # Add the new element now
            chunk_elems = list(overlap_elems) + [elements[read_idx]]
            chunk_tok = overlap_tok + et_next
            read_idx += 1
            new_in_chunk = [elements[read_idx - 1]]

        # Find the best semantic boundary within new_in_chunk (BR-50).
        # We search for cut points in the combined overlap+new array relative
        # to the non-overlap portion.
        best_cut: Optional[int] = None  # index into `new_in_chunk` to cut at (exclusive)
        best_priority: int = -1

        for i in range(1, len(new_in_chunk) + 1):
            # Position i in new_in_chunk corresponds to global index
            # (overlap_count + i - 1) and (overlap_count + i) in chunk_elems
            global_i = overlap_count + i  # boundary after the i-th new element
            prio = _boundary_priority_at(chunk_elems, global_i)
            # D5 atomicity guard: never cut immediately after a structured table element.
            # Cutting there would place it on the overlap tail and semantically split
            # the cell-batch unit across chunk boundaries.
            elem_before_cut = new_in_chunk[i - 1]
            if _is_structured_table(elem_before_cut):
                prio = 0  # suppress as a valid split point
            if prio > best_priority:
                best_priority = prio
                best_cut = i  # cut after i new elements

        # Use the best semantic boundary if one was found, else use full new list
        if best_cut is not None and best_priority >= 1 and best_cut < len(new_in_chunk):
            actual_new = new_in_chunk[:best_cut]
        else:
            actual_new = new_in_chunk  # fall through: use all that fit

        # Emit chunk
        actual_chunk_elems = list(overlap_elems) + actual_new
        new_tok = sum(estimate_tokens(e.content) for e in actual_new)

        chunks.append(ChunkRecord(
            chunk_index=chunk_index,
            token_span=(global_token_offset, global_token_offset + new_tok),
            elements=actual_chunk_elems,
            overlap_tokens=overlap_tok if chunk_index > 0 else 0,
            overlap_element_count=overlap_count,
        ))

        # Advance past the new elements we consumed in this chunk
        new_start += len(actual_new)
        global_token_offset += new_tok

        # Build overlap tail from the new elements of this chunk (BR-47)
        overlap_elems, overlap_tok = _build_overlap_tail(actual_new, overlap_tokens)

        chunk_index += 1

        if chunk_index > max_chunks:
            break  # safety valve

    return chunks


# ---------------------------------------------------------------------------
# Reassembly (data-shape §Reassembly contract)
# ---------------------------------------------------------------------------

def reassemble_document(doc: TranslatableDocument, chunks: List[ChunkRecord]) -> None:
    """Merge translated chunks back into the document in-place.

    Overlap de-duplication rule: for each non-first chunk, drop the
    leading overlap_element_count elements from the chunk's element list
    before appending (data-shape §Reassembly contract).

    The document's elements list is rebuilt in chunk_index ascending order.
    Same object references are preserved — no copy of element data.
    """
    if not chunks:
        return

    # Sort by chunk_index for correctness
    ordered = sorted(chunks, key=lambda c: c.chunk_index)

    # Track which element ids have already been included (de-dup guard)
    included_ids: set = set()
    result_elements: List[TranslatableElement] = []

    for chunk in ordered:
        # For non-first chunks, skip the overlap head
        start = chunk.overlap_element_count if chunk.chunk_index > 0 else 0
        for elem in chunk.elements[start:]:
            if elem.element_id not in included_ids:
                result_elements.append(elem)
                included_ids.add(elem.element_id)

    # Restore any elements that were not included in any chunk
    # (e.g., should_translate=False elements that weren't in any chunk boundary window)
    all_doc_ids = {e.element_id for e in doc.elements}
    missing_ids = all_doc_ids - included_ids
    if missing_ids:
        missing_elems = [e for e in doc.elements if e.element_id in missing_ids]
        result_elements.extend(missing_elems)

    doc.elements = result_elements
