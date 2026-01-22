"""Base parser interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.backend.models.translatable_document import TranslatableDocument


class BaseParser(ABC):
    """Abstract base class for document parsers.

    All parsers must implement the parse() method to convert a document
    file into a TranslatableDocument structure.
    """

    @abstractmethod
    def parse(self, file_path: str) -> TranslatableDocument:
        """Parse a document file.

        Args:
            file_path: Path to the document file.

        Returns:
            TranslatableDocument containing all translatable elements.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file format is not supported.
        """
        ...

    @property
    @abstractmethod
    def supported_extensions(self) -> list[str]:
        """List of supported file extensions (e.g., ['.pdf'])."""
        ...
