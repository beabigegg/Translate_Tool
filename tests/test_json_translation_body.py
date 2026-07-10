"""TDD tests for the body-path JSON envelope (BR-112).

Wires `translate_merged_paragraphs` (translation_helpers.py, IP-7) to a fake
LLMClient exposing both `translate_json` and `translate_once`, so these tests
exercise the ACTUAL flag-branch wiring, not `json_translation.py` in
isolation (that module's pure functions are covered directly in
test_json_translation_prompt.py's phrasing tests and inline below).

Anti-tautology: fallback/log assertions filter `record.name == "TranslateTool"`
(caplog attaches to root; a bare check would silently pass on any logger).
"""

from __future__ import annotations

import json
import logging
from typing import List, Optional, Tuple

import pytest

from app.backend import config
from app.backend.utils import json_translation
from app.backend.utils.logging_utils import logger as translate_tool_logger
from app.backend.utils.translation_helpers import translate_merged_paragraphs

GENUINE_SEGMENT = "The quality management system shall be reviewed at planned intervals."


class _JsonBodyClient:
    """LLMClient double exposing translate_json (happy/fallback path) and
    translate_once (the plain-text fallback target)."""

    def __init__(self, json_reply: Optional[str], json_ok: bool = True, fallback_reply: str = "FALLBACK_RESULT"):
        self.json_reply = json_reply
        self.json_ok = json_ok
        self.fallback_reply = fallback_reply
        self.json_calls: List[str] = []
        self.once_calls: List[str] = []

    def translate_json(self, user_payload: str, cancel_event=None, system_context=None) -> Tuple[bool, str]:
        self.json_calls.append(user_payload)
        return self.json_ok, self.json_reply

    def translate_once(self, text: str, tgt: str, src_lang, cancel_event=None, system_context=None) -> Tuple[bool, str]:
        self.once_calls.append(text)
        return True, self.fallback_reply


def _sent_body_json(payload: str) -> dict:
    """Extract the `{"text": ...}` JSON appended at the end of the built payload."""
    return json.loads(payload.rsplit("\n\n", 1)[1])


# ---------------------------------------------------------------------------
# AC-3: body envelope — send {"text": ...}, parse {"translation": ...}
# ---------------------------------------------------------------------------

class TestBodyEnvelope:
    def test_body_payload_sends_text_key_parses_translation_key(self, monkeypatch):
        monkeypatch.setattr(config, "JSON_STRUCTURED_TRANSLATION_ENABLED", True)
        client = _JsonBodyClient(json_reply=json.dumps({"translation": "翻譯結果"}))

        results = translate_merged_paragraphs([GENUINE_SEGMENT], "zh", "en", client)

        assert len(client.json_calls) == 1, "translate_json must be called exactly once"
        assert _sent_body_json(client.json_calls[0]) == {"text": GENUINE_SEGMENT}
        assert client.once_calls == [], "no fallback should fire on a valid reply"
        assert results == [(True, "翻譯結果")]

    def test_schema_rejects_missing_translation_key(self, monkeypatch):
        monkeypatch.setattr(config, "JSON_STRUCTURED_TRANSLATION_ENABLED", True)
        client = _JsonBodyClient(
            json_reply=json.dumps({"not_translation": "x"}),
            fallback_reply="FALLBACK_AFTER_SCHEMA_REJECT",
        )

        results = translate_merged_paragraphs([GENUINE_SEGMENT], "zh", "en", client)

        assert len(client.once_calls) == 1, "missing 'translation' key must trigger the fallback"
        assert results == [(True, "FALLBACK_AFTER_SCHEMA_REJECT")]

    def test_parse_body_reply_direct_missing_key(self):
        translation, reason = json_translation.parse_body_reply(
            json.dumps({"not_translation": "x"}), GENUINE_SEGMENT
        )
        assert translation is None
        assert reason

    def test_parse_body_reply_direct_echoed_source_rejected(self):
        translation, reason = json_translation.parse_body_reply(
            json.dumps({"translation": GENUINE_SEGMENT}), GENUINE_SEGMENT
        )
        assert translation is None
        assert "echo" in reason.lower()

    def test_parse_body_reply_direct_valid(self):
        translation, reason = json_translation.parse_body_reply(
            json.dumps({"translation": "翻譯"}), GENUINE_SEGMENT
        )
        assert translation == "翻譯"
        assert reason == ""


# ---------------------------------------------------------------------------
# AC-4: never-fail fallback (unparseable / empty content / echoed source)
# ---------------------------------------------------------------------------

class TestBodyFallback:
    def test_unparseable_json_falls_back_to_translate_once(self, monkeypatch):
        monkeypatch.setattr(config, "JSON_STRUCTURED_TRANSLATION_ENABLED", True)
        client = _JsonBodyClient(json_reply="not valid json at all", fallback_reply="PLAIN_TEXT_RESULT")

        results = translate_merged_paragraphs([GENUINE_SEGMENT], "zh", "en", client)

        assert client.once_calls == [GENUINE_SEGMENT], (
            "the plain-text translate_once call must fire with the original segment"
        )
        assert results == [(True, "PLAIN_TEXT_RESULT")]

    def test_empty_content_falls_back_to_translate_once(self, monkeypatch):
        monkeypatch.setattr(config, "JSON_STRUCTURED_TRANSLATION_ENABLED", True)
        client = _JsonBodyClient(json_reply="", json_ok=False, fallback_reply="RECOVERED_FROM_EMPTY")

        results = translate_merged_paragraphs([GENUINE_SEGMENT], "zh", "en", client)

        assert client.once_calls == [GENUINE_SEGMENT]
        assert results == [(True, "RECOVERED_FROM_EMPTY")]

    def test_echoed_source_falls_back_to_translate_once(self, monkeypatch):
        monkeypatch.setattr(config, "JSON_STRUCTURED_TRANSLATION_ENABLED", True)
        client = _JsonBodyClient(
            json_reply=json.dumps({"translation": GENUINE_SEGMENT}),
            fallback_reply="REAL_TRANSLATION",
        )

        results = translate_merged_paragraphs([GENUINE_SEGMENT], "zh", "en", client)

        assert client.once_calls == [GENUINE_SEGMENT], "echoed source must trigger the fallback"
        assert results == [(True, "REAL_TRANSLATION")]

    def test_job_completes_normally_on_corrupted_json(self, monkeypatch):
        """The job never fails on a malformed JSON reply — no exception
        propagates and the segment still resolves to a real result."""
        monkeypatch.setattr(config, "JSON_STRUCTURED_TRANSLATION_ENABLED", True)
        client = _JsonBodyClient(json_reply="{corrupted, not json", fallback_reply="RECOVERED")

        results = translate_merged_paragraphs([GENUINE_SEGMENT], "zh", "en", client)

        assert results == [(True, "RECOVERED")]

    def test_fallback_emits_info_via_translatetool_logger(self, monkeypatch, caplog):
        monkeypatch.setattr(config, "JSON_STRUCTURED_TRANSLATION_ENABLED", True)
        client = _JsonBodyClient(json_reply="not json", fallback_reply="X")

        with caplog.at_level(logging.INFO, logger="TranslateTool"):
            translate_merged_paragraphs(
                [GENUINE_SEGMENT], "zh", "en", client, log=translate_tool_logger.info,
            )

        info_records = [
            r for r in caplog.records
            if r.name == "TranslateTool" and r.levelno == logging.INFO
        ]
        assert any(
            "fallback" in r.message.lower() or "json" in r.message.lower()
            for r in info_records
        ), f"Expected an INFO fallback line on the TranslateTool logger; got {[r.message for r in info_records]}"

    def test_empty_content_ok_true_falls_back_to_translate_once(self, monkeypatch):
        """Distinct from the ok=False empty-reply case above: the transport
        call itself succeeds (ok=True) but returns an empty `content` string
        — the real gpt-oss:120b reasoning-model failure mode for the body
        path, mirrored from the table path's identical trigger."""
        monkeypatch.setattr(config, "JSON_STRUCTURED_TRANSLATION_ENABLED", True)
        client = _JsonBodyClient(json_reply="", json_ok=True, fallback_reply="RECOVERED_FROM_EMPTY_OK_TRUE")

        results = translate_merged_paragraphs([GENUINE_SEGMENT], "zh", "en", client)

        assert client.once_calls == [GENUINE_SEGMENT]
        assert results == [(True, "RECOVERED_FROM_EMPTY_OK_TRUE")]

    @pytest.mark.parametrize(
        "wrong_type_translation",
        [
            pytest.param(12345, id="int"),
            pytest.param(["a", "list"], id="list"),
            pytest.param(None, id="none"),
            pytest.param({"nested": "dict"}, id="dict"),
        ],
    )
    def test_wrong_type_translation_falls_back_to_translate_once(self, monkeypatch, wrong_type_translation):
        """BR-112: a schema-valid JSON envelope whose `translation` value is
        not a string (int / list / None / nested object) must fall back to
        plain-text translate_once, exactly like a missing key."""
        monkeypatch.setattr(config, "JSON_STRUCTURED_TRANSLATION_ENABLED", True)
        client = _JsonBodyClient(
            json_reply=json.dumps({"translation": wrong_type_translation}),
            fallback_reply="FALLBACK_AFTER_WRONG_TYPE",
        )

        results = translate_merged_paragraphs([GENUINE_SEGMENT], "zh", "en", client)

        assert client.once_calls == [GENUINE_SEGMENT], (
            f"a non-string translation value ({wrong_type_translation!r}) must trigger the fallback"
        )
        assert results == [(True, "FALLBACK_AFTER_WRONG_TYPE")]

    def test_meta_refusal_inside_valid_json_still_caught(self, monkeypatch):
        """BR-108 widened: a meta/refusal reply wrapped in schema-valid,
        non-echoed JSON must still be discarded in favor of the source."""
        monkeypatch.setattr(config, "JSON_STRUCTURED_TRANSLATION_ENABLED", True)
        client = _JsonBodyClient(
            json_reply=json.dumps({"translation": "I need more context to translate this"}),
        )

        results = translate_merged_paragraphs(["Executive Summary:"], "zh-TW", "en", client)

        assert client.once_calls == [], "a well-formed JSON reply must not trigger the plain-text fallback"
        assert results == [(True, "Executive Summary:")], (
            "the meta-refusal wrapped in valid JSON must be discarded in favor of the source"
        )


# ---------------------------------------------------------------------------
# Resilience: per-trigger INFO log line (BR-109) + job-never-raises sweep
# ---------------------------------------------------------------------------

class TestBodyFallbackReasonLogging:
    """For EACH BR-112 fallback trigger, assert the INFO line reaches the
    TranslateTool logger and carries the "[JSON-BODY] fallback to plain-text
    translate_once:" prefix (pinned verbatim from translation_helpers.py's
    `_translate_body_json`) — never a bare non-empty-string check."""

    @pytest.mark.parametrize(
        "json_reply,json_ok",
        [
            pytest.param("not valid json at all", True, id="unparseable-json"),
            pytest.param("", False, id="transport-ok-false"),
            pytest.param("", True, id="empty-content-ok-true"),
            pytest.param(json.dumps({"not_translation": "x"}), True, id="missing-translation-key"),
            pytest.param(json.dumps({"translation": 999}), True, id="wrong-type-translation"),
            pytest.param(json.dumps({"translation": GENUINE_SEGMENT}), True, id="echoed-source"),
        ],
    )
    def test_each_fallback_trigger_emits_info_line_with_prefix_and_reason(
        self, monkeypatch, caplog, json_reply, json_ok,
    ):
        monkeypatch.setattr(config, "JSON_STRUCTURED_TRANSLATION_ENABLED", True)
        client = _JsonBodyClient(json_reply=json_reply, json_ok=json_ok, fallback_reply="X")

        with caplog.at_level(logging.INFO, logger="TranslateTool"):
            translate_merged_paragraphs(
                [GENUINE_SEGMENT], "zh", "en", client, log=translate_tool_logger.info,
            )

        info_records = [
            r for r in caplog.records
            if r.name == "TranslateTool" and r.levelno == logging.INFO
        ]
        matching = [
            r for r in info_records
            if r.message.startswith("[JSON-BODY] fallback to plain-text translate_once:")
        ]
        assert matching, (
            f"expected an INFO line prefixed '[JSON-BODY] fallback to plain-text "
            f"translate_once:' for reply={json_reply!r} ok={json_ok}; "
            f"got: {[r.message for r in info_records]}"
        )
        # The reason portion (after the prefix) must be non-empty — a bare
        # prefix with nothing naming the actual reason is not acceptable.
        reason_part = matching[0].message.split(":", 1)[-1].strip()
        assert reason_part, "the log line must name a concrete reason, not be empty after the prefix"

    def test_job_never_raises_across_all_hostile_replies(self, monkeypatch):
        """The never-fail-fallback guarantee (BR-112), swept across every
        trigger shape in one pass: no exception ever propagates and every
        segment resolves to a real (non-None) result."""
        monkeypatch.setattr(config, "JSON_STRUCTURED_TRANSLATION_ENABLED", True)
        hostile_replies = [
            ("", True),
            ("", False),
            ("not json", True),
            ('{"cells": [{"row": 0, "col": 0, "translat', True),
            (json.dumps({"not_translation": "x"}), True),
            (json.dumps({"translation": 12345}), True),
            (json.dumps({"translation": None}), True),
            (json.dumps({"translation": GENUINE_SEGMENT}), True),
            (json.dumps({"translation": "I need more context to translate this"}), True),
        ]
        for reply, ok in hostile_replies:
            client = _JsonBodyClient(json_reply=reply, json_ok=ok, fallback_reply="RECOVERED")
            try:
                results = translate_merged_paragraphs([GENUINE_SEGMENT], "zh", "en", client)
            except Exception as exc:  # pragma: no cover - test failure path
                pytest.fail(f"job raised for hostile reply {reply!r} (ok={ok}): {exc!r}")
            assert len(results) == 1
            success, translated = results[0]
            assert success is True
            assert translated is not None and translated != ""


# ---------------------------------------------------------------------------
# Flag-OFF: byte-for-byte legacy plain-text path (Resolution A)
# ---------------------------------------------------------------------------

class TestFlagOffLegacyPath:
    def test_flag_off_never_calls_translate_json(self, monkeypatch):
        monkeypatch.setattr(config, "JSON_STRUCTURED_TRANSLATION_ENABLED", False)
        client = _JsonBodyClient(json_reply=json.dumps({"translation": "should not be used"}))

        results = translate_merged_paragraphs([GENUINE_SEGMENT], "zh", "en", client)

        assert client.json_calls == [], "flag OFF must never call translate_json"
        assert client.once_calls == [GENUINE_SEGMENT]
        assert results == [(True, "FALLBACK_RESULT")]
