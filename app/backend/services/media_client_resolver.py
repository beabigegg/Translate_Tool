"""Minimal LLM client resolver for the media (STT + translation) pipeline.

Deliberately does NOT reuse or modify processors/orchestrator.py:511-587 — that
logic is the document pipeline's cloud/fallback-chain client resolution,
coupled to BR-16/AC-5/AC-6 and a large existing test suite. This replicates
only the minimal subset a single-file media job needs: resolve model/profile
via provider_override or model_router.resolve_route_groups(), then build one
client (no num_ctx/VRAM bounds checking, no multi-provider fallback-chain
health-probe walk — both document-pipeline-specific).
"""

from __future__ import annotations

from typing import Callable, List, Optional, Tuple

from app.backend.clients.base_llm_client import LLMClient
from app.backend.clients.ollama_client import OllamaClient
from app.backend.clients.openai_compatible_client import OpenAICompatibleClient
from app.backend.config import DEFAULT_MODEL, load_providers_config
from app.backend.services.model_router import resolve_route_groups
from app.backend.translation_profiles import get_profile
from app.backend.utils.logging_utils import logger


def _build_cloud_client(
    provider_id: str,
    model: str,
    provider_config: dict,
    api_key_override: Optional[str],
    system_prompt: str,
    log: Callable[[str], None],
) -> Optional[OpenAICompatibleClient]:
    providers = {p["id"]: p for p in provider_config.get("providers", [])}
    prov = providers.get(provider_id)
    enabled = prov.get("enabled") is True if prov else False
    if not prov or not (enabled or api_key_override):
        return None
    effective_key = api_key_override if api_key_override else prov.get("api_key", "")
    try:
        return OpenAICompatibleClient(
            base_url=prov["base_url"],
            api_key=effective_key,
            model=model,
            provider_id=provider_id,
            verify_ssl=prov.get("tls_verify", True),
            system_prompt=system_prompt,
        )
    except Exception as exc:
        log(f"[MEDIA-PROVIDER] Failed to build cloud client for {provider_id}: {exc}; falling back to Ollama")
        logger.warning("[MEDIA-PROVIDER] Failed to build cloud client for %s: %s", provider_id, exc)
        return None


def resolve_media_client(
    provider_override: Optional[str],
    model_override: Optional[str],
    profile: Optional[str],
    api_key_override: Optional[str],
    targets: List[str],
    log: Callable[[str], None] = lambda s: None,
) -> Tuple[LLMClient, str]:
    """Resolve a single LLMClient + model name for a media translation job.

    Mirrors api/routes.py:171-228's manual-override/auto-routing split, reduced
    to one client for the whole job (no per-target-group multi-model dispatch —
    the document pipeline's route_groups loop is out of scope here).
    """
    provider_config = load_providers_config()

    if provider_override and provider_override != "auto":
        if not provider_config:
            raise ValueError("No providers configured")
        providers = {p["id"]: p for p in provider_config.get("providers", [])}
        prov = providers.get(provider_override)
        if not prov:
            raise ValueError(f"Unknown provider '{provider_override}'")
        model = model_override or prov.get("models", {}).get("translate") or DEFAULT_MODEL
        system_prompt = get_profile(profile).system_prompt
        if provider_override == "ollama-local":
            client = OllamaClient(model=model, system_prompt=system_prompt, log=log)
            return client, model
        # Route through _build_cloud_client (not an inline duplicate) so a
        # manually-overridden provider is subject to the SAME enabled-flag
        # check as the auto-routing branch below — an admin disabling a
        # provider in providers.yml (enabled: false) must not be bypassable
        # by explicitly requesting it via provider_override. Falls back to
        # Ollama, mirroring orchestrator.py:511-587's document-pipeline
        # behavior for a disabled/unreachable cloud provider.
        client = _build_cloud_client(provider_override, model, provider_config, api_key_override, system_prompt, log)
        if client is not None:
            log(f"[MEDIA-PROVIDER] Using cloud provider: {provider_override} model={model}")
            return client, model
        log(f"[MEDIA-PROVIDER] Provider '{provider_override}' is disabled or unreachable — falling back to ollama-local")
        client = OllamaClient(model=model, system_prompt=system_prompt, log=log)
        return client, model

    route_groups = resolve_route_groups(targets, profile_override=profile, provider_config=provider_config)

    if route_groups is None:
        # Explicit non-auto profile (routes.py:198-225): apply its system prompt,
        # but still prefer cloud routing for the model when providers.yml is set.
        explicit_profile = get_profile(profile)
        cloud_groups = (
            resolve_route_groups(targets, profile_override=None, provider_config=provider_config)
            if provider_config else None
        )
        if cloud_groups:
            model = model_override or cloud_groups[0].model
            provider_id = cloud_groups[0].provider
        else:
            model = model_override or explicit_profile.model
            provider_id = "ollama-local"
        system_prompt = explicit_profile.system_prompt
    elif route_groups:
        group = route_groups[0]
        model = model_override or group.model
        provider_id = group.provider
        system_prompt = get_profile(group.profile_id).system_prompt
    else:
        model = model_override or DEFAULT_MODEL
        provider_id = "ollama-local"
        system_prompt = get_profile(profile).system_prompt

    if provider_id and provider_id != "ollama-local" and provider_config:
        client = _build_cloud_client(provider_id, model, provider_config, api_key_override, system_prompt, log)
        if client is not None:
            return client, model

    client = OllamaClient(model=model, system_prompt=system_prompt, log=log)
    log("[MEDIA-PROVIDER] Primary translation client: ollama-local")
    return client, model
