"""Base renderer interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING, Dict

if TYPE_CHECKING:
    from app.backend.models.translatable_document import TranslatableDocument


class RenderMode(Enum):
    """Output rendering mode."""

    INLINE = "inline"  # Insert translation after original (default for DOCX)
    SIDE_BY_SIDE = "side_by_side"  # Original and translation in parallel columns/pages
    OVERLAY = "overlay"  # Replace original text with translation at same position


class BaseRenderer(ABC):
    """Abstract base class for document renderers.

    Renderers take a TranslatableDocument with translations applied
    and produce output in a specific format.
    """

    @abstractmethod
    def render(
        self,
        document: "TranslatableDocument",
        output_path: str,
        translations: Dict[str, str],
        mode: RenderMode = RenderMode.INLINE,
    ) -> None:
        """Render a translated document to output.

        Args:
            document: TranslatableDocument with source content.
            output_path: Path for the output file.
            translations: Mapping from original text to translated text.
            mode: Rendering mode to use.

        Raises:
            ValueError: If the mode is not supported by this renderer.
            IOError: If the output file cannot be written.
        """
        ...

    @property
    @abstractmethod
    def supported_modes(self) -> list[RenderMode]:
        """List of rendering modes supported by this renderer."""
        ...

    @property
    @abstractmethod
    def output_extension(self) -> str:
        """File extension for output (e.g., '.docx', '.pdf')."""
        ...

    def supports_mode(self, mode: RenderMode) -> bool:
        """Check if this renderer supports a given mode."""
        return mode in self.supported_modes
