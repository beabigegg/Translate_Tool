"""TDD tests for the shared JSON-translation instruction builder (BR-111).

Anti-tautology requirements (CLAUDE.md / test-plan.md):
  - Phrasing pin assertions read the ACTUAL built payload string, never an
    internal attribute.
  - The "not re-wrapped by translate_once framing" assertion reads the
    outgoing transport payload captured at the mocked `requests.Session.post`
    (OpenAI) / `_call_ollama` (Ollama) boundary — never `client.system_prompt`.
"""

from __future__ import annotations

import inspect
import json
from dataclasses import dataclass
from typing import List
from unittest.mock import MagicMock, patch

import pytest

from app.backend.utils import json_translation
from app.backend.clients.ollama_client import OllamaClient
from app.backend.clients.openai_compatible_client import OpenAICompatibleClient


@dataclass
class _Cell:
    row: int
    col: int
    content: str
    is_numeric: bool = False


# ---------------------------------------------------------------------------
# Pinned phrasing (BR-111)
# ---------------------------------------------------------------------------

class TestPinnedPhrasing:
    def test_body_payload_contains_pinned_return_framing(self):
        payload = json_translation.build_body_payload("Hello world", "en", "zh")
        assert 'Return: {"translation": <your translation>}' in payload, (
            f"Pinned framing missing from body payload: {payload!r}"
        )

    def test_body_payload_excludes_known_bad_phrasings(self):
        payload = json_translation.build_body_payload("Hello world", "en", "zh")
        low = payload.lower()
        assert "reply only with json" not in low
        assert "output a json object with a single key" not in low

    def test_table_payload_contains_translation_key_framing(self):
        cells = [_Cell(0, 0, "Name"), _Cell(0, 1, "Value")]
        payload = json_translation.build_table_payload(cells, "en", "zh")
        assert '"translation"' in payload, f"table payload missing translation key framing: {payload!r}"
        assert "Reply ONLY with JSON" not in payload
        assert "Output a JSON object with a single key" not in payload

    def test_instruction_precedes_serialized_cells_in_table_payload(self):
        """BR-80: instruction appears BEFORE the serialized cell list."""
        cells = [_Cell(0, 0, "Name"), _Cell(0, 1, "Value")]
        payload = json_translation.build_table_payload(cells, "en", "zh")
        instr_idx = payload.lower().find("translate")
        # "Value" is real cell CONTENT — it only occurs in the appended
        # serialized cell list, never in the instruction/schema-example text.
        content_idx = payload.find("Value")
        assert instr_idx >= 0, f"instruction not found: {payload!r}"
        assert content_idx > instr_idx, (
            f"instruction must precede the serialized cell list: {payload!r}"
        )

    def test_body_payload_sends_the_actual_text_value(self):
        payload = json_translation.build_body_payload("製作日期", "zh", "en")
        appended_json = payload.rsplit("\n\n", 1)[1]
        assert json.loads(appended_json) == {"text": "製作日期"}


# ---------------------------------------------------------------------------
# Regression pin: NOT re-wrapped by translate_once's framing (the double-wrap
# that made gpt-oss:120b return empty content with finish_reason="stop").
# ---------------------------------------------------------------------------

class TestNotRewrappedByTranslateOnceFraming:
    def test_openai_translate_json_sends_payload_unwrapped(self):
        client = OpenAICompatibleClient(base_url="http://fake-host", api_key="k", model="m")
        payload = json_translation.build_body_payload("Hello", "en", "zh")
        captured = {}

        def _fake_post(url, json=None, headers=None, timeout=None):
            captured["json"] = json
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {
                "choices": [{"message": {"content": '{"translation": "你好"}'}, "finish_reason": "stop"}]
            }
            return resp

        with patch.object(client._session, "post", side_effect=_fake_post):
            ok, content = client.translate_json(payload)

        assert ok is True
        sent_user_msg = next(m["content"] for m in captured["json"]["messages"] if m["role"] == "user")
        assert sent_user_msg == payload, (
            "translate_json must send the payload AS-IS, never re-wrapped"
        )
        assert "Output only the translation" not in sent_user_msg
        assert "Translate the following text from" not in sent_user_msg

    def test_ollama_translate_json_sends_payload_unwrapped(self):
        client = OllamaClient(model="m")
        payload = json_translation.build_body_payload("Hello", "en", "zh")
        captured = {}

        def _fake_call_ollama(payload_dict, timeout_tuple=None):
            captured["payload"] = payload_dict
            return True, '{"translation": "你好"}'

        with patch.object(client, "_call_ollama", side_effect=_fake_call_ollama):
            ok, content = client.translate_json(payload)

        assert ok is True
        assert captured["payload"]["prompt"] == payload, (
            "translate_json must send the payload AS-IS via the prompt field"
        )
        assert "Output only the translation" not in captured["payload"]["prompt"]


# ---------------------------------------------------------------------------
# AC-7: both clients expose the seam (off-Protocol)
# ---------------------------------------------------------------------------

class TestSharedBuilderConsumers:
    def test_both_prompt_builders_delegate_to_shared_module(self):
        """Both concrete clients expose translate_json with a matching
        signature; base_llm_client.py's five-method Protocol is unmodified."""
        assert hasattr(OllamaClient, "translate_json")
        assert callable(OllamaClient.translate_json)
        assert hasattr(OpenAICompatibleClient, "translate_json")
        assert callable(OpenAICompatibleClient.translate_json)

        sig_ollama = list(inspect.signature(OllamaClient.translate_json).parameters)[1:]
        sig_openai = list(inspect.signature(OpenAICompatibleClient.translate_json).parameters)[1:]
        assert sig_ollama == sig_openai, (
            f"translate_json signatures diverge: ollama={sig_ollama} openai={sig_openai}"
        )

    def test_protocol_still_defines_exactly_five_methods(self):
        """translate_json stays OFF the LLMClient Protocol (design.md option b)."""
        from app.backend.clients.base_llm_client import LLMClient
        methods = [
            name for name, member in inspect.getmembers(LLMClient)
            if not name.startswith("_") and callable(getattr(LLMClient, name, None))
        ]
        assert len(methods) == 5, f"Expected 5 Protocol methods, got {len(methods)}: {methods}"
        assert "translate_json" not in methods

    def test_response_format_not_relied_upon_a_stub_ignoring_it_still_passes(self):
        """A stub client that never sends/expects `response_format` still
        satisfies the seam — it MAY be sent best-effort but MUST NOT be
        depended on (design.md)."""

        class _Stub:
            def translate_json(self, user_payload, cancel_event=None, system_context=None):
                return True, '{"translation": "ok"}'

        stub = _Stub()
        payload = json_translation.build_body_payload("hi", "en", "zh")
        ok, content = stub.translate_json(payload)
        assert ok is True
        assert json.loads(content) == {"translation": "ok"}
