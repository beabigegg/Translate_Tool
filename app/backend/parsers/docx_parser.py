"""DOCX parser for extracting translatable content.

This module parses DOCX files and extracts text content with structure
information into a TranslatableDocument format.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any, Iterator, List, Optional, Set, Tuple

import docx
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.backend.config import MAX_SEGMENTS, MAX_TEXT_LENGTH
from app.backend.models.translatable_document import (
    DocumentMetadata,
    ElementType,
    PageInfo,
    TranslatableDocument,
    TranslatableElement,
)
from app.backend.parsers.base import BaseParser
from app.backend.utils.exceptions import check_document_size_limits
from app.backend.utils.text_utils import has_cjk, should_translate

logger = logging.getLogger(__name__)

# Marker used to identify previously inserted translations
INSERT_MARKER = "\u200b"


class DocxParser(BaseParser):
    """Parser for DOCX documents.

    Extracts text from paragraphs, tables, and text boxes into
    a unified TranslatableDocument format.
    """

    def __init__(
        self,
        max_segments: int = MAX_SEGMENTS,
        max_text_length: int = MAX_TEXT_LENGTH,
        skip_inserted_translations: bool = True,
    ):
        """Initialize the parser.

        Args:
            max_segments: Maximum number of segments to extract.
            max_text_length: Maximum total text length.
            skip_inserted_translations: Skip paragraphs that appear to be
                previously inserted translations (contain INSERT_MARKER).
        """
        self.max_segments = max_segments
        self.max_text_length = max_text_length
        self.skip_inserted_translations = skip_inserted_translations

    @property
    def supported_extensions(self) -> list[str]:
        """Supported file extensions."""
        return [".docx"]

    def parse(self, file_path: str) -> TranslatableDocument:
        """Parse a DOCX file.

        Args:
            file_path: Path to the DOCX file.

        Returns:
            TranslatableDocument with extracted elements.

        Raises:
            FileNotFoundError: If file does not exist.
            ValueError: If file is not a DOCX.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        if path.suffix.lower() != ".docx":
            raise ValueError(f"Not a DOCX file: {file_path}")

        doc = docx.Document(file_path)

        elements: List[TranslatableElement] = []
        seen_keys: Set[str] = set()
        total_text_length = 0

        # Extract from body (paragraphs, tables, SDT)
        body_elements = self._extract_from_container(
            doc._body, "Body", seen_keys, total_text_length
        )
        elements.extend(body_elements)
        total_text_length += sum(len(e.content) for e in body_elements)

        # Extract from text boxes
        textbox_elements = self._extract_from_textboxes(doc, seen_keys)
        elements.extend(textbox_elements)
        total_text_length += sum(len(e.content) for e in textbox_elements)

        # Validate document size
        check_document_size_limits(
            segment_count=len(elements),
            total_text_length=total_text_length,
            max_segments=self.max_segments,
            max_text_length=self.max_text_length,
            document_type="Word document",
        )

        # Build metadata
        core_props = doc.core_properties
        metadata = DocumentMetadata(
            title=core_props.title,
            author=core_props.author,
            subject=core_props.subject,
            page_count=1,  # DOCX doesn't expose page count easily
            has_text_layer=True,
        )

        # DOCX doesn't have clear page boundaries, use single page
        pages = [PageInfo(page_num=1, width=612, height=792)]

        return TranslatableDocument(
            source_path=file_path,
            source_type="docx",
            elements=elements,
            pages=pages,
            metadata=metadata,
        )

    def _extract_from_container(
        self,
        container: Any,
        context: str,
        seen_keys: Set[str],
        current_length: int,
    ) -> List[TranslatableElement]:
        """Extract elements from a container (body, cell, etc.).

        Args:
            container: Container object with _element attribute.
            context: Context string for logging.
            seen_keys: Set of already-seen paragraph keys.
            current_length: Current total text length.

        Returns:
            List of extracted elements.
        """
        elements: List[TranslatableElement] = []

        if container._element is None:
            return elements

        for child_element in container._element:
            qname = child_element.tag

            if qname.endswith("}p"):
                # Paragraph
                p = Paragraph(child_element, container)
                elem = self._extract_paragraph(p, context, seen_keys)
                if elem:
                    elements.append(elem)

            elif qname.endswith("}tbl"):
                # Table
                table = Table(child_element, container)
                for r_idx, row in enumerate(table.rows, 1):
                    for c_idx, cell in enumerate(row.cells, 1):
                        cell_ctx = f"{context} > Tbl(r{r_idx},c{c_idx})"
                        cell_elements = self._extract_from_container(
                            cell, cell_ctx, seen_keys, current_length
                        )
                        # Mark as table cells
                        for elem in cell_elements:
                            elem.element_type = ElementType.TABLE_CELL
                            elem.metadata["in_table"] = True
                            elem.metadata["row"] = r_idx
                            elem.metadata["col"] = c_idx
                        elements.extend(cell_elements)

            elif qname.endswith("}sdt"):
                # Structured Document Tag (content controls)
                sdt_elements = self._extract_from_sdt(
                    child_element, f"{context} > SDT", seen_keys
                )
                elements.extend(sdt_elements)

        return elements

    def _extract_paragraph(
        self,
        p: Paragraph,
        context: str,
        seen_keys: Set[str],
    ) -> Optional[TranslatableElement]:
        """Extract a single paragraph.

        Args:
            p: Paragraph object.
            context: Context string.
            seen_keys: Set of already-seen keys.

        Returns:
            TranslatableElement or None if should be skipped.
        """
        text = self._get_paragraph_text(p)
        if not text.strip():
            return None

        # Skip if it's our inserted translation
        if self.skip_inserted_translations and self._is_inserted_translation(p):
            return None

        # Generate key for deduplication
        key = self._get_paragraph_key(p, text)
        if key in seen_keys:
            return None
        seen_keys.add(key)

        # Determine element type based on style
        element_type = self._classify_paragraph_type(p)

        return TranslatableElement(
            element_id=f"docx_{uuid.uuid4().hex[:8]}",
            content=text,
            element_type=element_type,
            page_num=1,  # DOCX doesn't have clear page numbers
            should_translate=True,
            metadata={
                "context": context,
                "style": p.style.name if p.style else None,
                "paragraph_ref": p,  # Keep reference for rendering
            },
        )

    def _extract_from_sdt(
        self,
        sdt_element: Any,
        context: str,
        seen_keys: Set[str],
    ) -> List[TranslatableElement]:
        """Extract from Structured Document Tag.

        Args:
            sdt_element: SDT XML element.
            context: Context string.
            seen_keys: Set of already-seen keys.

        Returns:
            List of extracted elements.
        """
        elements: List[TranslatableElement] = []
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

        # Extract placeholder text
        placeholder_texts = []
        for t in sdt_element.xpath(".//w:placeholder//w:t", namespaces=ns):
            if t.text:
                placeholder_texts.append(t.text)

        if placeholder_texts:
            full_placeholder = "".join(placeholder_texts).strip()
            if full_placeholder:
                elements.append(
                    TranslatableElement(
                        element_id=f"sdt_ph_{uuid.uuid4().hex[:8]}",
                        content=full_placeholder,
                        element_type=ElementType.TEXT,
                        page_num=1,
                        should_translate=True,
                        metadata={"context": f"{context}-Placeholder", "sdt_type": "placeholder"},
                    )
                )

        # Extract dropdown items
        list_items = []
        for item in sdt_element.xpath(".//w:dropDownList/w:listItem", namespaces=ns):
            display_text = item.get(qn("w:displayText"))
            if display_text:
                list_items.append(display_text)

        if list_items:
            elements.append(
                TranslatableElement(
                    element_id=f"sdt_dd_{uuid.uuid4().hex[:8]}",
                    content="\n".join(list_items),
                    element_type=ElementType.LIST_ITEM,
                    page_num=1,
                    should_translate=True,
                    metadata={"context": f"{context}-Dropdown", "sdt_type": "dropdown"},
                )
            )

        # Extract content from sdtContent
        sdt_content = sdt_element.find(qn("w:sdtContent"))
        if sdt_content is not None:
            # Create wrapper for recursive processing
            class SdtContentWrapper:
                def __init__(self, element, parent):
                    self._element = element
                    self._parent = parent

            wrapper = SdtContentWrapper(sdt_content, None)
            content_elements = self._extract_from_container(
                wrapper, context, seen_keys, 0
            )
            elements.extend(content_elements)

        return elements

    def _extract_from_textboxes(
        self,
        doc: Any,
        seen_keys: Set[str],
    ) -> List[TranslatableElement]:
        """Extract text from text boxes.

        Args:
            doc: DOCX document object.
            seen_keys: Set of already-seen keys.

        Returns:
            List of extracted elements.
        """
        elements: List[TranslatableElement] = []

        for txbx, text in self._iter_textbox_texts(doc):
            if not text.strip():
                continue

            # Check if should translate
            if not (has_cjk(text) or should_translate(text, "auto")):
                continue

            key = f"txbx_{hash(text)}_{len(text)}"
            if key in seen_keys:
                continue
            seen_keys.add(key)

            elements.append(
                TranslatableElement(
                    element_id=f"txbx_{uuid.uuid4().hex[:8]}",
                    content=text,
                    element_type=ElementType.TEXT,
                    page_num=1,
                    should_translate=True,
                    metadata={
                        "context": "TextBox",
                        "textbox_ref": txbx,  # Keep reference for rendering
                    },
                )
            )

        return elements

    def _iter_textbox_texts(self, doc: Any) -> Iterator[Tuple[Any, str]]:
        """Iterate over text boxes and their content.

        Args:
            doc: DOCX document object.

        Yields:
            Tuples of (textbox_element, text_content).
        """
        for tx in doc._element.xpath(".//*[local-name()='txbxContent']"):
            kept = []
            for p in tx.xpath(".//*[local-name()='p']"):
                text = self._get_textbox_paragraph_text(p)
                if not text.strip():
                    continue
                # Skip our inserted translations
                if INSERT_MARKER in text:
                    continue
                for line in text.split("\n"):
                    if line.strip():
                        kept.append(line.strip())

            if kept:
                yield tx, "\n".join(kept)

    def _get_paragraph_text(self, p: Paragraph) -> str:
        """Get text from a paragraph, preserving line breaks.

        Args:
            p: Paragraph object.

        Returns:
            Text content with line breaks.
        """
        parts = []
        for node in p._p.xpath(".//*[local-name()='t' or local-name()='br' or local-name()='tab']"):
            tag = node.tag.split("}", 1)[-1]
            if tag == "t":
                parts.append(node.text or "")
            elif tag == "br":
                parts.append("\n")
            else:  # tab
                parts.append(" ")
        return "".join(parts).strip()

    def _get_textbox_paragraph_text(self, p_element: Any) -> str:
        """Get text from a textbox paragraph element.

        Args:
            p_element: Paragraph XML element.

        Returns:
            Text content.
        """
        parts = []
        for node in p_element.xpath(".//*[local-name()='t' or local-name()='br' or local-name()='tab']"):
            tag = node.tag.split("}", 1)[-1]
            if tag == "t":
                parts.append(node.text or "")
            elif tag == "br":
                parts.append("\n")
            else:
                parts.append(" ")
        return "".join(parts)

    def _is_inserted_translation(self, p: Paragraph) -> bool:
        """Check if paragraph is an inserted translation.

        Args:
            p: Paragraph to check.

        Returns:
            True if this is an inserted translation paragraph.
        """
        return any(INSERT_MARKER in (r.text or "") for r in p.runs)

    def _get_paragraph_key(self, p: Paragraph, text: str) -> str:
        """Generate a unique key for a paragraph.

        Args:
            p: Paragraph object.
            text: Paragraph text.

        Returns:
            Unique key string.
        """
        try:
            xml_content = p._p.xml if hasattr(p._p, "xml") else str(p._p)
            return f"{hash(xml_content)}_{len(text)}_{text[:50]}"
        except (AttributeError, TypeError):
            return f"fallback_{hash(text)}_{len(text)}"

    def _classify_paragraph_type(self, p: Paragraph) -> ElementType:
        """Classify paragraph type based on style.

        Args:
            p: Paragraph to classify.

        Returns:
            ElementType for the paragraph.
        """
        style_name = p.style.name.lower() if p.style else ""

        if "heading" in style_name or "title" in style_name:
            return ElementType.TITLE
        if "header" in style_name:
            return ElementType.HEADER
        if "footer" in style_name:
            return ElementType.FOOTER
        if "caption" in style_name:
            return ElementType.CAPTION
        if "list" in style_name:
            return ElementType.LIST_ITEM

        return ElementType.TEXT
