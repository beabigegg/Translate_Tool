"""Unit tests for model_router.py."""

from __future__ import annotations

import pytest

from app.backend.services.model_router import (
    RouteGroup,
    resolve_route_groups,
    GREEDY_PRESET,
    TGEMMA_DEFAULT_MODEL,
    RouteDecision,
    get_route_info,
    resolve_route,
)
from app.backend.config import DEFAULT_MODEL, HYMT_DEFAULT_MODEL


class TestResolveRoute:
    def test_vietnamese_routes_to_hymt(self):
        decision = resolve_route(["Vietnamese"])
        assert decision is not None
        assert decision.model == HYMT_DEFAULT_MODEL
        assert decision.model_type == "translation"
        assert decision.target == "Vietnamese"

    def test_english_routes_to_qwen(self):
        decision = resolve_route(["English"])
        assert decision is not None
        assert decision.model == DEFAULT_MODEL
        assert decision.profile_id == "general"
        assert decision.model_type == "general"

    def test_japanese_routes_to_hymt(self):
        decision = resolve_route(["Japanese"])
        assert decision is not None
        assert decision.model == HYMT_DEFAULT_MODEL

    def test_korean_routes_to_tgemma(self):
        decision = resolve_route(["Korean"])
        assert decision is not None
        assert decision.model == TGEMMA_DEFAULT_MODEL
        assert decision.model_type == "general"

    def test_unlisted_language_defaults_to_qwen(self):
        decision = resolve_route(["Swahili"])
        assert decision is not None
        assert decision.model == DEFAULT_MODEL
        assert decision.profile_id == "general"

    def test_empty_targets_defaults_to_qwen(self):
        decision = resolve_route([])
        assert decision is not None
        assert decision.model == DEFAULT_MODEL

    def test_multi_target_routes_by_first(self):
        decision = resolve_route(["Vietnamese", "English"])
        assert decision is not None
        assert decision.model == HYMT_DEFAULT_MODEL
        assert decision.target == "Vietnamese"

    def test_manual_override_returns_none(self):
        decision = resolve_route(["Vietnamese"], profile_override="general")
        assert decision is None

    def test_auto_override_routes_normally(self):
        decision = resolve_route(["Vietnamese"], profile_override="auto")
        assert decision is not None
        assert decision.model == HYMT_DEFAULT_MODEL

    def test_no_override_routes_normally(self):
        decision = resolve_route(["Japanese"], profile_override=None)
        assert decision is not None
        assert decision.model == HYMT_DEFAULT_MODEL


class TestGreedyPreset:
    def test_greedy_temperature(self):
        assert GREEDY_PRESET["temperature"] == 0.05

    def test_greedy_top_p(self):
        assert GREEDY_PRESET["top_p"] == 0.50

    def test_greedy_top_k(self):
        assert GREEDY_PRESET["top_k"] == 10

    def test_greedy_repeat_penalty(self):
        assert GREEDY_PRESET["repeat_penalty"] == 1.0

    def test_greedy_frequency_penalty(self):
        assert GREEDY_PRESET["frequency_penalty"] == 0.0


class TestGetRouteInfo:
    def test_single_target(self):
        info = get_route_info(["Vietnamese"])
        assert len(info) == 1
        assert info[0]["target"] == "Vietnamese"
        assert info[0]["model"] == HYMT_DEFAULT_MODEL
        assert info[0]["is_primary"] is True

    def test_multiple_targets(self):
        info = get_route_info(["English", "Vietnamese", "Japanese"])
        assert len(info) == 3
        assert info[0]["target"] == "English"
        assert info[0]["is_primary"] is True
        assert info[1]["target"] == "Vietnamese"
        assert info[1]["is_primary"] is False
        assert info[2]["target"] == "Japanese"
        assert info[2]["is_primary"] is False

    def test_response_fields(self):
        info = get_route_info(["Vietnamese"])
        entry = info[0]
        assert "target" in entry
        assert "model" in entry
        assert "profile_id" in entry
        assert "model_type" in entry
        assert "is_primary" in entry


class TestResolveRouteGroups:
    def test_english_vietnamese_gives_two_groups(self):
        groups = resolve_route_groups(["English", "Vietnamese"])
        assert groups is not None
        assert len(groups) == 2
        models = {g.model for g in groups}
        assert DEFAULT_MODEL in models
        assert HYMT_DEFAULT_MODEL in models

    def test_english_group_targets(self):
        groups = resolve_route_groups(["English", "Vietnamese"])
        assert groups is not None
        qwen_group = next(g for g in groups if g.model == DEFAULT_MODEL)
        assert qwen_group.targets == ["English"]

    def test_vietnamese_group_targets(self):
        groups = resolve_route_groups(["English", "Vietnamese"])
        assert groups is not None
        hymt_group = next(g for g in groups if g.model == HYMT_DEFAULT_MODEL)
        assert hymt_group.targets == ["Vietnamese"]

    def test_vietnamese_japanese_german_gives_one_group(self):
        groups = resolve_route_groups(["Vietnamese", "Japanese", "German"])
        assert groups is not None
        assert len(groups) == 1
        assert groups[0].model == HYMT_DEFAULT_MODEL
        assert set(groups[0].targets) == {"Vietnamese", "Japanese", "German"}

    def test_mixed_three_languages_two_groups(self):
        groups = resolve_route_groups(["English", "Vietnamese", "Japanese"])
        assert groups is not None
        assert len(groups) == 2

    def test_insertion_order_preserved(self):
        groups = resolve_route_groups(["English", "Vietnamese", "Japanese"])
        assert groups is not None
        assert groups[0].model == DEFAULT_MODEL
        assert groups[1].model == HYMT_DEFAULT_MODEL

    def test_manual_override_returns_none(self):
        result = resolve_route_groups(["English", "Vietnamese"], profile_override="general")
        assert result is None

    def test_auto_override_routes_normally(self):
        result = resolve_route_groups(["English", "Vietnamese"], profile_override="auto")
        assert result is not None
        assert len(result) == 2

    def test_empty_targets_returns_empty_list(self):
        result = resolve_route_groups([])
        assert result == []

    def test_route_group_has_correct_profile_id(self):
        groups = resolve_route_groups(["Vietnamese"])
        assert groups is not None
        assert groups[0].profile_id == "technical_process"
        assert groups[0].model_type == "translation"

    def test_unlisted_language_uses_default_route(self):
        groups = resolve_route_groups(["Swahili"])
        assert groups is not None
        assert len(groups) == 1
        assert groups[0].model == DEFAULT_MODEL
        assert groups[0].profile_id == "general"


# ---------------------------------------------------------------------------
# p1-cloud-providers AC-4: Config-driven routing (providers.yml replaces
# hardcoded _ROUTING_TABLE).  These tests must FAIL before IP-3 is implemented.
# ---------------------------------------------------------------------------

class TestConfigDrivenRouting:
    """Verify that model_router reads routing from ProviderConfig / providers.yml."""

    def test_resolve_route_uses_providers_yml(self, tmp_path, monkeypatch):
        """resolve_route honours routing.default.model from providers.yml."""
        import importlib
        import app.backend.services.model_router as mr_module

        yml_content = (
            "providers:\n"
            "  - id: panjit\n"
            "    type: openai\n"
            "    enabled: true\n"
            "    base_url: http://example.com\n"
            "    api_key: testkey\n"
            "    models:\n"
            "      translate: cloud-model-xl\n"
            "routing:\n"
            "  default:\n"
            "    model: cloud-model-xl\n"
            "    provider: panjit\n"
            "    profile: general\n"
            "fallback_chain: [panjit]\n"
        )
        yml = tmp_path / "providers.yml"
        yml.write_text(yml_content)

        from app.backend.config import load_providers_config
        config = load_providers_config(config_path=yml)
        assert config is not None

        # resolve_route must accept provider config and use it
        decision = resolve_route(["English"], provider_config=config)
        assert decision is not None
        assert decision.model == "cloud-model-xl"
        assert decision.provider == "panjit"

    def test_hardcoded_routing_table_removed(self):
        """_ROUTING_TABLE must no longer be a module-level dict in model_router."""
        import app.backend.services.model_router as mr_module

        # After IP-3 the hardcoded _ROUTING_TABLE is removed
        assert not hasattr(mr_module, "_ROUTING_TABLE"), (
            "_ROUTING_TABLE must be removed from model_router (hardcoded table gone)"
        )

    def test_default_route_from_config(self, tmp_path, monkeypatch):
        """Routing default falls back to config's routing.default when target is unlisted."""
        yml_content = (
            "providers:\n"
            "  - id: panjit\n"
            "    type: openai\n"
            "    enabled: true\n"
            "    base_url: http://example.com\n"
            "    api_key: testkey\n"
            "    models:\n"
            "      translate: cloud-model-xl\n"
            "routing:\n"
            "  default:\n"
            "    model: cloud-model-xl\n"
            "    provider: panjit\n"
            "    profile: general\n"
            "fallback_chain: [panjit]\n"
        )
        yml = tmp_path / "providers.yml"
        yml.write_text(yml_content)

        from app.backend.config import load_providers_config
        config = load_providers_config(config_path=yml)

        decision = resolve_route(["Swahili"], provider_config=config)
        assert decision is not None
        assert decision.model == "cloud-model-xl"
        assert decision.provider == "panjit"

    def test_provider_field_present_in_route_decision(self, tmp_path):
        """RouteDecision must have a 'provider' field after IP-3."""
        yml_content = (
            "providers:\n"
            "  - id: panjit\n"
            "    type: openai\n"
            "    enabled: true\n"
            "    base_url: http://example.com\n"
            "    api_key: testkey\n"
            "    models:\n"
            "      translate: cloud-model-xl\n"
            "routing:\n"
            "  default:\n"
            "    model: cloud-model-xl\n"
            "    provider: panjit\n"
            "    profile: general\n"
            "fallback_chain: [panjit]\n"
        )
        yml = tmp_path / "providers.yml"
        yml.write_text(yml_content)

        from app.backend.config import load_providers_config
        config = load_providers_config(config_path=yml)

        decision = resolve_route(["English"], provider_config=config)
        assert decision is not None
        assert hasattr(decision, "provider"), (
            "RouteDecision must have a 'provider' field (AC-4)"
        )
        assert decision.provider is not None


# ---------------------------------------------------------------------------
# Helper: build a providers.yml dict with routing.rules for tests.
# Never reads real config/providers.yml — uses tmp_path fixture inline.
# ---------------------------------------------------------------------------

def _build_config(tmp_path, rules: dict, default_model="fallback-model", default_provider="cloud-prov"):
    """Write a providers.yml with given routing.rules to tmp_path and load it."""
    rules_block = ""
    if rules:
        rules_block = "  rules:\n"
        for lang, entry in rules.items():
            rules_block += f"    {lang}:\n"
            rules_block += f"      model: {entry['model']}\n"
            rules_block += f"      provider: {entry['provider']}\n"
            if "profile" in entry:
                rules_block += f"      profile: {entry['profile']}\n"

    yml_content = (
        "providers:\n"
        "  - id: cloud-prov\n"
        "    type: openai\n"
        "    enabled: true\n"
        "    base_url: http://example.com\n"
        "    api_key: testkey\n"
        "    models:\n"
        "      translate: fallback-model\n"
        "routing:\n"
        f"  default:\n"
        f"    model: {default_model}\n"
        f"    provider: {default_provider}\n"
        f"    profile: general\n"
        f"{rules_block}"
        "fallback_chain: [cloud-prov]\n"
    )
    yml = tmp_path / "providers.yml"
    yml.write_text(yml_content)
    from app.backend.config import load_providers_config
    return load_providers_config(config_path=yml)


# ---------------------------------------------------------------------------
# AC-1, AC-2, AC-5: routing.rules consumed from config
# ---------------------------------------------------------------------------

class TestProviderRoutingRules:
    """Tests that routing.rules entries are read from config and used per-language."""

    def test_routing_rules_key_consumed_from_config(self, tmp_path):
        """resolve_route picks per-language rule, not routing.default, when rule exists (AC-1)."""
        config = _build_config(
            tmp_path,
            rules={
                "Vietnamese": {"model": "vi-model", "provider": "cloud-prov"},
            },
            default_model="fallback-model",
        )
        decision = resolve_route(["Vietnamese"], provider_config=config)
        assert decision is not None
        assert decision.model == "vi-model", (
            f"Expected vi-model from routing.rules, got {decision.model}"
        )

    def test_config_only_change_routes_new_language(self, tmp_path):
        """Adding a new language to routing.rules routes it without any code change (AC-2)."""
        config = _build_config(
            tmp_path,
            rules={
                "Klingon": {"model": "klingon-model", "provider": "cloud-prov"},
            },
            default_model="fallback-model",
        )
        decision = resolve_route(["Klingon"], provider_config=config)
        assert decision is not None
        assert decision.model == "klingon-model", (
            f"Expected klingon-model from routing.rules, got {decision.model}"
        )

    def test_unlisted_language_falls_back_to_default(self, tmp_path):
        """A language not in routing.rules falls back to routing.default (AC-5)."""
        config = _build_config(
            tmp_path,
            rules={
                "Vietnamese": {"model": "vi-model", "provider": "cloud-prov"},
            },
            default_model="fallback-model",
        )
        decision = resolve_route(["Swahili"], provider_config=config)
        assert decision is not None
        assert decision.model == "fallback-model", (
            f"Expected fallback-model from routing.default, got {decision.model}"
        )

    def test_default_fallback_no_crash(self, tmp_path):
        """Missing language in routing.rules must not raise and must return a valid RouteGroup (AC-5)."""
        config = _build_config(tmp_path, rules={}, default_model="fallback-model")
        try:
            decision = resolve_route(["Klingon"], provider_config=config)
        except Exception as exc:
            raise AssertionError(f"resolve_route raised unexpectedly: {exc}") from exc
        assert decision is not None
        assert isinstance(decision, RouteDecision)


# ---------------------------------------------------------------------------
# AC-3, AC-4: per-language independent resolution in resolve_route_groups
# ---------------------------------------------------------------------------

class TestResolveRouteGroupsPerLanguage:
    """Tests that resolve_route_groups resolves each target_lang independently."""

    def test_each_target_resolved_independently(self, tmp_path):
        """Two languages with distinct rules → two RouteGroups (AC-3)."""
        config = _build_config(
            tmp_path,
            rules={
                "Vietnamese": {"model": "vi-model", "provider": "cloud-prov"},
                "German": {"model": "de-model", "provider": "cloud-prov"},
            },
            default_model="fallback-model",
        )
        groups = resolve_route_groups(["Vietnamese", "German"], provider_config=config)
        assert groups is not None
        assert len(groups) == 2, (
            f"Expected 2 groups for distinct-model languages, got {len(groups)}: "
            f"{[(g.model, g.targets) for g in groups]}"
        )

    def test_first_target_not_used_for_all(self, tmp_path):
        """German is NOT used for Vietnamese targets — second lang resolves independently (AC-3)."""
        config = _build_config(
            tmp_path,
            rules={
                "German": {"model": "de-model", "provider": "cloud-prov"},
                "Vietnamese": {"model": "vi-model", "provider": "cloud-prov"},
            },
            default_model="fallback-model",
        )
        groups = resolve_route_groups(["German", "Vietnamese"], provider_config=config)
        assert groups is not None
        # "Vietnamese" must NOT appear in the German group
        de_group = next((g for g in groups if g.model == "de-model"), None)
        assert de_group is not None, "de-model group not found"
        assert "Vietnamese" not in de_group.targets, (
            f"Vietnamese incorrectly placed in German group: {de_group.targets}"
        )

    def test_mixed_batch_vi_de_ko_ja_groups(self, tmp_path):
        """Mixed [vi, de, ko, ja] batch partitions into groups by their distinct rule models (AC-4)."""
        config = _build_config(
            tmp_path,
            rules={
                "Vietnamese": {"model": "vi-model", "provider": "cloud-prov"},
                "German": {"model": "de-model", "provider": "cloud-prov"},
                "Korean": {"model": "ko-model", "provider": "cloud-prov"},
                "Japanese": {"model": "ja-model", "provider": "cloud-prov"},
            },
            default_model="fallback-model",
        )
        groups = resolve_route_groups(
            ["Vietnamese", "German", "Korean", "Japanese"], provider_config=config
        )
        assert groups is not None
        # All 4 languages should have distinct models → 4 groups
        assert len(groups) >= 2, f"Expected at least 2 groups, got {len(groups)}"
        # All languages must appear somewhere in the groups
        all_targets = [t for g in groups for t in g.targets]
        assert set(all_targets) == {"Vietnamese", "German", "Korean", "Japanese"}, (
            f"Not all languages in groups: {all_targets}"
        )

    def test_mixed_batch_group_models_match_rules(self, tmp_path):
        """For each group, the model matches the fixture routing.rule for its target(s) (AC-4 contract)."""
        rules = {
            "Vietnamese": {"model": "vi-model", "provider": "cloud-prov"},
            "German": {"model": "de-model", "provider": "cloud-prov"},
            "Korean": {"model": "ko-model", "provider": "cloud-prov"},
            "Japanese": {"model": "ja-model", "provider": "cloud-prov"},
        }
        config = _build_config(tmp_path, rules=rules, default_model="fallback-model")
        groups = resolve_route_groups(
            ["Vietnamese", "German", "Korean", "Japanese"], provider_config=config
        )
        assert groups is not None
        for group in groups:
            for target in group.targets:
                expected_model = rules[target]["model"]
                assert group.model == expected_model, (
                    f"Target {target!r}: expected model {expected_model!r}, got {group.model!r}"
                )


# ---------------------------------------------------------------------------
# AC-6 regression: legacy Ollama path when provider_config=None
# ---------------------------------------------------------------------------

class TestLegacyOllamaPath:
    """Regression: provider_config=None still uses _OLLAMA_ROUTING_TABLE."""

    def test_provider_config_none_uses_ollama_grouping(self):
        """Without provider_config, resolve_route_groups uses legacy Ollama grouping (AC-6)."""
        # Vietnamese, German, Japanese all map to HYMT in legacy table → 1 group
        groups = resolve_route_groups(
            ["Vietnamese", "German", "Japanese"], provider_config=None
        )
        assert groups is not None
        assert len(groups) == 1, (
            f"Legacy path: vi/de/ja should share one HYMT group, got {len(groups)}"
        )
        assert groups[0].model == HYMT_DEFAULT_MODEL

    def test_legacy_single_language_batch(self):
        """Single target, provider_config=None returns exactly one group."""
        groups = resolve_route_groups(["Vietnamese"], provider_config=None)
        assert groups is not None
        assert len(groups) == 1

    def test_legacy_profile_override_non_auto_returns_none(self):
        """provider_config=None, profile_override='general' → None (AC-6)."""
        result = resolve_route_groups(
            ["Vietnamese"], profile_override="general", provider_config=None
        )
        assert result is None
