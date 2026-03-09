"""Benchmark-driven model routing for automatic model selection per target language."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from app.backend.config import DEFAULT_MODEL, HYMT_DEFAULT_MODEL

# TranslateGemma model — best for Korean (benchmark March 2026)
import os
TGEMMA_DEFAULT_MODEL = os.environ.get("TGEMMA_DEFAULT_MODEL", "translategemma:4b")

# Greedy decode preset — universally optimal across all models (benchmark March 2026)
GREEDY_PRESET: Dict[str, object] = {
    "temperature": 0.05,
    "top_p": 0.50,
    "top_k": 10,
    "repeat_penalty": 1.0,
    "frequency_penalty": 0.0,
}

# Routing table: target_language -> (model, profile_id, model_type)
# Unlisted languages fall back to DEFAULT_ROUTE (Qwen3.5:4b / general).
# Benchmark rationale:
#   HY-MT: best for zh->vi, zh->de, zh->ja (Qwen catastrophic at zh->ja=11.97)
#   TranslateGemma: marginally best for zh->ko
#   Qwen3.5:4b: best for zh->en and most other directions
_ROUTING_TABLE: Dict[str, Tuple[str, str, str]] = {
    "Vietnamese": (HYMT_DEFAULT_MODEL, "technical_process", "translation"),
    "German": (HYMT_DEFAULT_MODEL, "technical_process", "translation"),
    "Japanese": (HYMT_DEFAULT_MODEL, "technical_process", "translation"),
    "Korean": (TGEMMA_DEFAULT_MODEL, "general", "general"),
}

_DEFAULT_ROUTE: Tuple[str, str, str] = (DEFAULT_MODEL, "general", "general")


@dataclass(frozen=True)
class RouteDecision:
    """Resolved routing decision for a translation job."""

    target: str
    model: str
    profile_id: str
    model_type: str


@dataclass
class RouteGroup:
    """A group of target languages sharing the same (model, profile_id, model_type) routing."""

    targets: List[str] = field(default_factory=list)
    model: str = ""
    profile_id: str = ""
    model_type: str = ""
    refine_model: Optional[str] = None  # Cross-model refiner (None = no refinement)


def resolve_route(targets: List[str], profile_override: Optional[str] = None) -> Optional[RouteDecision]:
    """Return routing decision for the given targets.

    If profile_override is a non-empty string other than "auto", returns None
    so the caller can apply the explicit profile instead.
    """
    if profile_override and profile_override.lower() != "auto":
        return None

    first_target = targets[0] if targets else ""
    model, profile_id, model_type = _ROUTING_TABLE.get(first_target, _DEFAULT_ROUTE)
    return RouteDecision(
        target=first_target,
        model=model,
        profile_id=profile_id,
        model_type=model_type,
    )


def resolve_route_groups(
    targets: List[str],
    profile_override: Optional[str] = None,
) -> Optional[List[RouteGroup]]:
    """Group targets by optimal (model, profile_id, model_type), preserving insertion order.

    Returns None if profile_override is a non-auto explicit profile ID, signalling the
    caller to create a single group using the override profile's model.
    """
    if profile_override and profile_override.lower() != "auto":
        return None

    if not targets:
        return []

    # Preserve insertion order while grouping by routing key
    seen: Dict[Tuple[str, str, str], RouteGroup] = {}
    for target in targets:
        key = _ROUTING_TABLE.get(target, _DEFAULT_ROUTE)
        if key not in seen:
            model, profile_id, model_type = key
            # HY-MT and TranslateGemma groups get Qwen as cross-model refiner.
            # Qwen group (DEFAULT_ROUTE) keeps refine_model=None (no self-refinement).
            if key != _DEFAULT_ROUTE:
                refine_model: Optional[str] = DEFAULT_MODEL
            else:
                refine_model = None
            seen[key] = RouteGroup(
                targets=[], model=model, profile_id=profile_id,
                model_type=model_type, refine_model=refine_model,
            )
        seen[key].targets.append(target)

    return list(seen.values())


def get_route_info(targets: List[str]) -> List[Dict[str, str]]:
    """Return per-target routing info (for the /api/route-info endpoint).

    Always uses auto-routing regardless of any override.
    The first target is the primary one used for the job.
    """
    result = []
    for i, target in enumerate(targets):
        model, profile_id, model_type = _ROUTING_TABLE.get(target, _DEFAULT_ROUTE)
        result.append({
            "target": target,
            "model": model,
            "profile_id": profile_id,
            "model_type": model_type,
            "is_primary": i == 0,
        })
    return result
