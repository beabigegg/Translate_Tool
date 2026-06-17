"""Config-driven model routing for automatic model selection per target language.

p1-cloud-providers: routing now reads from ProviderConfig (providers.yml) instead
of the hardcoded ``_ROUTING_TABLE``.  If no provider_config is supplied the
functions fall back to Ollama-local behaviour (backward-compatible with existing
callers that do not pass a config).

The ``routing.rules`` key is schema-tolerated but NOT consumed here — it is owned
by ``p1-provider-routing``.  The schema is parsed and ignored.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.backend.config import DEFAULT_MODEL, HYMT_DEFAULT_MODEL

# TranslateGemma model — best for Korean (benchmark March 2026)
TGEMMA_DEFAULT_MODEL = os.environ.get("TGEMMA_DEFAULT_MODEL", "translategemma:4b")

# Greedy decode preset — universally optimal across all models (benchmark March 2026)
GREEDY_PRESET: Dict[str, object] = {
    "temperature": 0.05,
    "top_p": 0.50,
    "top_k": 10,
    "repeat_penalty": 1.0,
    "frequency_penalty": 0.0,
}

# ---------------------------------------------------------------------------
# Legacy Ollama routing table — used ONLY when no provider_config is supplied.
# This preserves backward compatibility for callers that haven't migrated yet.
# When providers.yml is loaded and injected via provider_config, this table
# is bypassed entirely.
# ---------------------------------------------------------------------------
_OLLAMA_ROUTING_TABLE: Dict[str, Tuple[str, str, str]] = {
    "Vietnamese": (HYMT_DEFAULT_MODEL, "technical_process", "translation"),
    "German": (HYMT_DEFAULT_MODEL, "technical_process", "translation"),
    "Japanese": (HYMT_DEFAULT_MODEL, "technical_process", "translation"),
    "Korean": (TGEMMA_DEFAULT_MODEL, "general", "general"),
}
_OLLAMA_DEFAULT_ROUTE: Tuple[str, str, str] = (DEFAULT_MODEL, "general", "general")
_OLLAMA_PROVIDER_ID = "ollama-local"


@dataclass(frozen=True)
class RouteDecision:
    """Resolved routing decision for a translation job."""

    target: str
    model: str
    profile_id: str
    model_type: str
    provider: Optional[str] = None  # p1-cloud-providers: winning provider ID


@dataclass
class RouteGroup:
    """A group of target languages sharing the same (model, profile_id, model_type) routing."""

    targets: List[str] = field(default_factory=list)
    model: str = ""
    profile_id: str = ""
    model_type: str = ""
    refine_model: Optional[str] = None  # Cross-model refiner (None = no refinement)
    provider: Optional[str] = None  # p1-cloud-providers: resolved provider ID


def _resolve_from_ollama_table(target: str) -> Tuple[str, str, str, str]:
    """Resolve (model, profile_id, model_type, provider) from the legacy Ollama table."""
    model, profile_id, model_type = _OLLAMA_ROUTING_TABLE.get(target, _OLLAMA_DEFAULT_ROUTE)
    return model, profile_id, model_type, _OLLAMA_PROVIDER_ID


def _resolve_from_config(
    target: str,
    provider_config: Dict[str, Any],
) -> Tuple[str, str, str, str]:
    """Resolve (model, profile_id, model_type, provider) from providers.yml config.

    Uses ``routing.default`` for all targets (per-language rules are owned by
    ``p1-provider-routing`` and are not consumed here).
    """
    routing = provider_config.get("routing", {})
    default = routing.get("default", {})
    model = default.get("model", DEFAULT_MODEL)
    provider_id = default.get("provider", _OLLAMA_PROVIDER_ID)
    profile = default.get("profile", "general")
    # Derive model_type from provider's model entry; default to "general"
    model_type = "general"
    providers = provider_config.get("providers", [])
    for p in providers:
        if p.get("id") == provider_id:
            models = p.get("models", {})
            # model_type hint: if a "translation" key exists and model matches, use translation
            if models.get("translate") == model and p.get("type") == "openai":
                model_type = "general"  # cloud providers don't distinguish general/translation
            break
    return model, profile, model_type, provider_id


def resolve_route(
    targets: List[str],
    profile_override: Optional[str] = None,
    provider_config: Optional[Dict[str, Any]] = None,
) -> Optional[RouteDecision]:
    """Return routing decision for the given targets.

    If profile_override is a non-empty string other than "auto", returns None
    so the caller can apply the explicit profile instead.

    Args:
        targets: List of target language names.
        profile_override: Optional profile override; None or "auto" → auto-route.
        provider_config: Optional parsed providers.yml config dict.  When None,
            falls back to the Ollama routing table (backward-compatible).
    """
    if profile_override and profile_override.lower() != "auto":
        return None

    first_target = targets[0] if targets else ""

    if provider_config:
        model, profile_id, model_type, provider_id = _resolve_from_config(
            first_target, provider_config
        )
    else:
        model, profile_id, model_type, provider_id = _resolve_from_ollama_table(first_target)

    return RouteDecision(
        target=first_target,
        model=model,
        profile_id=profile_id,
        model_type=model_type,
        provider=provider_id,
    )


def resolve_route_groups(
    targets: List[str],
    profile_override: Optional[str] = None,
    provider_config: Optional[Dict[str, Any]] = None,
) -> Optional[List[RouteGroup]]:
    """Group targets by optimal (model, profile_id, model_type), preserving insertion order.

    Returns None if profile_override is a non-auto explicit profile ID, signalling the
    caller to create a single group using the override profile's model.

    Args:
        targets: List of target language names.
        profile_override: Optional profile override.
        provider_config: Optional parsed providers.yml config dict.
    """
    if profile_override and profile_override.lower() != "auto":
        return None

    if not targets:
        return []

    if provider_config:
        # All targets use the same routing.default when providers.yml is active.
        # Per-language precise routing is owned by p1-provider-routing.
        model, profile_id, model_type, provider_id = _resolve_from_config(
            targets[0], provider_config
        )
        group = RouteGroup(
            targets=list(targets),
            model=model,
            profile_id=profile_id,
            model_type=model_type,
            refine_model=None,  # Cloud providers don't use cross-model refinement
            provider=provider_id,
        )
        return [group]

    # Legacy Ollama path: group by routing key, preserve insertion order
    seen: Dict[Tuple[str, str, str], RouteGroup] = {}
    for target in targets:
        ollama_key = _OLLAMA_ROUTING_TABLE.get(target, _OLLAMA_DEFAULT_ROUTE)
        if ollama_key not in seen:
            model, profile_id, model_type = ollama_key
            # HY-MT and TranslateGemma groups get Qwen as cross-model refiner.
            # Qwen group (DEFAULT_ROUTE) keeps refine_model=None (no self-refinement).
            if ollama_key != _OLLAMA_DEFAULT_ROUTE:
                refine_model: Optional[str] = DEFAULT_MODEL
            else:
                refine_model = None
            seen[ollama_key] = RouteGroup(
                targets=[],
                model=model,
                profile_id=profile_id,
                model_type=model_type,
                refine_model=refine_model,
                provider=_OLLAMA_PROVIDER_ID,
            )
        seen[ollama_key].targets.append(target)

    return list(seen.values())


def get_route_info(
    targets: List[str],
    provider_config: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Return per-target routing info (for the /api/route-info endpoint).

    Always uses auto-routing regardless of any override.
    The first target is the primary one used for the job.

    Args:
        targets: List of target language names.
        provider_config: Optional parsed providers.yml config dict.
    """
    result = []
    for i, target in enumerate(targets):
        if provider_config:
            model, profile_id, model_type, provider_id = _resolve_from_config(
                target, provider_config
            )
        else:
            model, profile_id, model_type, provider_id = _resolve_from_ollama_table(target)

        result.append({
            "target": target,
            "model": model,
            "profile_id": profile_id,
            "model_type": model_type,
            "is_primary": i == 0,
            "provider": provider_id,
        })
    return result
