"""Term data model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class Term:
    source_text: str
    target_text: str
    source_lang: str
    target_lang: str
    domain: str
    context_snippet: str = ""
    confidence: float = 1.0
    usage_count: int = 0
    created_at: Optional[str] = field(default=None)

    def __post_init__(self) -> None:
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc).isoformat()
