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
