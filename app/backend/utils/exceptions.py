"""Custom exceptions and validation helpers."""

from __future__ import annotations

from dataclasses import dataclass

from app.backend.config import MAX_SEGMENTS, MAX_TEXT_LENGTH


class ApiError(Exception):
    """API call error."""


@dataclass
class DocumentSizeLimitExceeded(Exception):
    """Raised when document size limits are exceeded."""

    message: str
    segment_count: int = 0
    text_length: int = 0
    max_segments: int = MAX_SEGMENTS
    max_text_length: int = MAX_TEXT_LENGTH
    limit_type: str = "unknown"

    def __str__(self) -> str:
        return self.message


def check_document_size_limits(
    segment_count: int,
    total_text_length: int,
    max_segments: int = MAX_SEGMENTS,
    max_text_length: int = MAX_TEXT_LENGTH,
    document_type: str = "document",
) -> None:
    if segment_count > max_segments:
        raise DocumentSizeLimitExceeded(
            f"{document_type} exceeds segment limit: {segment_count:,} > {max_segments:,}.",
            segment_count=segment_count,
            text_length=total_text_length,
            max_segments=max_segments,
            max_text_length=max_text_length,
            limit_type="segments",
        )

    if total_text_length > max_text_length:
        raise DocumentSizeLimitExceeded(
            f"{document_type} exceeds text length limit: {total_text_length:,} > {max_text_length:,}.",
            segment_count=segment_count,
            text_length=total_text_length,
            max_segments=max_segments,
            max_text_length=max_text_length,
            limit_type="text_length",
        )
