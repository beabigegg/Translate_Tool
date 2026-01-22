"""Translatable document data models.

This module defines the unified intermediate layer for document translation,
supporting coordinate-based layout preservation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ElementType(Enum):
    """Type of document element."""

    TEXT = "text"
    TITLE = "title"
    HEADER = "header"
    FOOTER = "footer"
    TABLE_CELL = "table_cell"
    LIST_ITEM = "list_item"
    CAPTION = "caption"
    FOOTNOTE = "footnote"


@dataclass
class BoundingBox:
    """Bounding box coordinates.

    Coordinate system: top-left origin, x increases right, y increases down.
    Unit: points (1 point = 1/72 inch).
    """

    x0: float  # Left
    y0: float  # Top
    x1: float  # Right
    y1: float  # Bottom

    @property
    def width(self) -> float:
        """Width of the bounding box."""
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        """Height of the bounding box."""
        return self.y1 - self.y0

    @property
    def center_x(self) -> float:
        """X coordinate of the center."""
        return (self.x0 + self.x1) / 2

    @property
    def center_y(self) -> float:
        """Y coordinate of the center."""
        return (self.y0 + self.y1) / 2

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            "x0": self.x0,
            "y0": self.y0,
            "x1": self.x1,
            "y1": self.y1,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> BoundingBox:
        """Create from dictionary."""
        return cls(
            x0=data["x0"],
            y0=data["y0"],
            x1=data["x1"],
            y1=data["y1"],
        )

    @classmethod
    def from_tuple(cls, coords: tuple) -> BoundingBox:
        """Create from (x0, y0, x1, y1) tuple."""
        return cls(x0=coords[0], y0=coords[1], x1=coords[2], y1=coords[3])


@dataclass
class StyleInfo:
    """Text style information."""

    font_name: Optional[str] = None
    font_size: Optional[float] = None
    is_bold: bool = False
    is_italic: bool = False
    color: Optional[str] = None  # Hex color code
    background_color: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "font_name": self.font_name,
            "font_size": self.font_size,
            "is_bold": self.is_bold,
            "is_italic": self.is_italic,
            "color": self.color,
            "background_color": self.background_color,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> StyleInfo:
        """Create from dictionary."""
        return cls(
            font_name=data.get("font_name"),
            font_size=data.get("font_size"),
            is_bold=data.get("is_bold", False),
            is_italic=data.get("is_italic", False),
            color=data.get("color"),
            background_color=data.get("background_color"),
        )


@dataclass
class TranslatableElement:
    """A translatable element in the document."""

    element_id: str
    content: str
    element_type: ElementType
    page_num: int
    bbox: Optional[BoundingBox] = None
    style: Optional[StyleInfo] = None
    should_translate: bool = True
    translated_content: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "element_id": self.element_id,
            "content": self.content,
            "element_type": self.element_type.value,
            "page_num": self.page_num,
            "bbox": self.bbox.to_dict() if self.bbox else None,
            "style": self.style.to_dict() if self.style else None,
            "should_translate": self.should_translate,
            "translated_content": self.translated_content,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TranslatableElement:
        """Create from dictionary."""
        return cls(
            element_id=data["element_id"],
            content=data["content"],
            element_type=ElementType(data["element_type"]),
            page_num=data["page_num"],
            bbox=BoundingBox.from_dict(data["bbox"]) if data.get("bbox") else None,
            style=StyleInfo.from_dict(data["style"]) if data.get("style") else None,
            should_translate=data.get("should_translate", True),
            translated_content=data.get("translated_content"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class PageInfo:
    """Information about a document page."""

    page_num: int
    width: float
    height: float
    rotation: int = 0  # Degrees: 0, 90, 180, 270

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "page_num": self.page_num,
            "width": self.width,
            "height": self.height,
            "rotation": self.rotation,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PageInfo:
        """Create from dictionary."""
        return cls(
            page_num=data["page_num"],
            width=data["width"],
            height=data["height"],
            rotation=data.get("rotation", 0),
        )


@dataclass
class DocumentMetadata:
    """Document-level metadata."""

    title: Optional[str] = None
    author: Optional[str] = None
    subject: Optional[str] = None
    creator: Optional[str] = None
    producer: Optional[str] = None
    creation_date: Optional[str] = None
    modification_date: Optional[str] = None
    page_count: int = 0
    has_text_layer: bool = True  # False for scanned PDFs

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "author": self.author,
            "subject": self.subject,
            "creator": self.creator,
            "producer": self.producer,
            "creation_date": self.creation_date,
            "modification_date": self.modification_date,
            "page_count": self.page_count,
            "has_text_layer": self.has_text_layer,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DocumentMetadata:
        """Create from dictionary."""
        return cls(
            title=data.get("title"),
            author=data.get("author"),
            subject=data.get("subject"),
            creator=data.get("creator"),
            producer=data.get("producer"),
            creation_date=data.get("creation_date"),
            modification_date=data.get("modification_date"),
            page_count=data.get("page_count", 0),
            has_text_layer=data.get("has_text_layer", True),
        )


@dataclass
class TranslatableDocument:
    """A document ready for translation."""

    source_path: str
    source_type: str  # pdf, docx, pptx, xlsx
    elements: List[TranslatableElement]
    pages: List[PageInfo]
    metadata: DocumentMetadata

    def get_translatable_elements(self) -> List[TranslatableElement]:
        """Get elements that should be translated."""
        return [e for e in self.elements if e.should_translate]

    def get_elements_by_page(self, page_num: int) -> List[TranslatableElement]:
        """Get elements on a specific page."""
        return [e for e in self.elements if e.page_num == page_num]

    def get_all_elements_by_page(self) -> Dict[int, List[TranslatableElement]]:
        """Get all elements grouped by page number.

        Returns:
            Dict mapping page numbers to lists of elements on that page.
        """
        result: Dict[int, List[TranslatableElement]] = {}
        for e in self.elements:
            if e.page_num not in result:
                result[e.page_num] = []
            result[e.page_num].append(e)
        return result

    def get_elements_in_reading_order(self) -> List[TranslatableElement]:
        """Get elements sorted by reading order (top-to-bottom, left-to-right)."""

        def sort_key(e: TranslatableElement) -> tuple:
            if e.bbox:
                return (e.page_num, e.bbox.y0, e.bbox.x0)
            return (e.page_num, 0, 0)

        return sorted(self.elements, key=sort_key)

    def get_unique_texts(self) -> List[str]:
        """Get unique translatable texts for deduplication."""
        seen = set()
        unique = []
        for e in self.get_translatable_elements():
            text = e.content.strip()
            if text and text not in seen:
                seen.add(text)
                unique.append(text)
        return unique

    def apply_translations(self, translations: Dict[str, str]) -> None:
        """Apply translated content to elements.

        Args:
            translations: Mapping from original text to translated text.
        """
        for element in self.elements:
            if element.should_translate:
                original = element.content.strip()
                if original in translations:
                    element.translated_content = translations[original]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "source_path": self.source_path,
            "source_type": self.source_type,
            "elements": [e.to_dict() for e in self.elements],
            "pages": [p.to_dict() for p in self.pages],
            "metadata": self.metadata.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TranslatableDocument:
        """Create from dictionary."""
        return cls(
            source_path=data["source_path"],
            source_type=data["source_type"],
            elements=[TranslatableElement.from_dict(e) for e in data["elements"]],
            pages=[PageInfo.from_dict(p) for p in data["pages"]],
            metadata=DocumentMetadata.from_dict(data["metadata"]),
        )
