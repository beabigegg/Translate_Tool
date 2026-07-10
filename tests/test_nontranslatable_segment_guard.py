"""Regression tests for the non-translatable body-segment guards (BR-107, BR-108).

Bug: a trivial/non-translatable body (non-table) segment on the
`translate_merged_paragraphs` -> `client.translate_once` path has no
input-side passthrough (unlike table cells, BR-68) and no output-side
guard against a model meta/refusal reply. A live cloud reply such as
"Could you please provide the text you'd like translated?" was written
verbatim into output in place of a trivial segment (8D PDF English run,
task 42265c0b).

Fixtures below marked "verbatim from the 8D PDF" were extracted with
PyMuPDF (`page.get_text("dict")` spans) from
`docs/TEST_DOC/CS2408-0021 ... -onepage.pdf` — the actual reproduction
document referenced in change-request.md. No standalone punctuation-only
span exists in that document, so PUNCTUATION_ONLY_SEGMENT is a synthetic
complement for that trivial class.

Mock boundary: a fake `LLMClient` implementing only `translate_once`
(the sole method `translate_merged_paragraphs` calls). Never patches
`translation_helpers` internals directly.
"""

from __future__ import annotations

import json
import threading
from typing import Dict, List, Optional, Tuple

from app.backend.utils.text_utils import is_meta_refusal
from app.backend.utils.translation_helpers import translate_merged_paragraphs

# ---------------------------------------------------------------------------
# Real 8D PDF fixture strings (verbatim, extracted via PyMuPDF from
# docs/TEST_DOC/CS2408-0021 ... -onepage.pdf)
# ---------------------------------------------------------------------------
PAGE_NUMBER_SEGMENT = "1"  # lone page-number span
ALREADY_ENGLISH_LABEL_SEGMENT = "Executive Summary:"  # already-English label span
SHORT_CODE_SEGMENT = "CS2408-0021"  # "CCR NO." value span — 2 letters only
SHORT_LOT_SEGMENT = "427M"  # "DC/LOT:" value span — 1 letter only
CJK_SENTENCE_SEGMENT = (
    "失效原因：弯脚模具废料卡料切伤材料本体，弯脚模移料拨齿回不"
    "到位，导致材料回吸偏位切伤本体。"
)  # substantial CJK sentence span — genuinely translatable

# Synthetic complements (no verbatim equivalent exists in the 8D PDF spans).
PUNCTUATION_ONLY_SEGMENT = "---"
WHITESPACE_ONLY_SEGMENT = "   "

# The exact meta/refusal reply recorded in the bug reproduction (8D run, task 42265c0b).
ASK_BACK_REPLY = "Could you please provide the text you'd like translated?"


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
def _extract_body_text(user_payload: str) -> str:
    """Recover the original segment from a `json_translation.build_body_payload`
    string (the `{"text": ...}` envelope is always the last `\\n\\n`-separated
    part — see json_translation.py)."""
    return json.loads(user_payload.rsplit("\n\n", 1)[1])["text"]


class FakeLLMClient:
    """Call-counting LLMClient double: always returns the same scripted reply.

    Implements BOTH `translate_once` (flag-OFF plain-text path) and
    `translate_json` (flag-ON default path, BR-111/BR-112) so this fake drives
    whichever path `translate_merged_paragraphs` takes under the default
    `JSON_STRUCTURED_TRANSLATION_ENABLED=True`. Both methods share the same
    `call_count`/`calls` bookkeeping so every existing assertion (call count,
    which text was/wasn't sent) holds regardless of which path fires.
    """

    def __init__(self, reply: str = "TRANSLATED", ok: bool = True) -> None:
        self.reply = reply
        self.ok = ok
        self.call_count = 0
        self.calls: List[str] = []

    def translate_once(
        self,
        text: str,
        tgt: str,
        src_lang: Optional[str],
        cancel_event: Optional[threading.Event] = None,
        system_context: Optional[str] = None,
    ) -> Tuple[bool, str]:
        self.call_count += 1
        self.calls.append(text)
        return self.ok, self.reply

    def translate_json(
        self,
        user_payload: str,
        cancel_event: Optional[threading.Event] = None,
        system_context: Optional[str] = None,
    ) -> Tuple[bool, str]:
        self.call_count += 1
        self.calls.append(_extract_body_text(user_payload))
        if not self.ok:
            return False, ""
        return True, json.dumps({"translation": self.reply})


class ScriptedLLMClient:
    """Call-counting LLMClient double: reply depends on the input segment.

    See `FakeLLMClient` docstring — implements both methods for the same
    reason.
    """

    def __init__(self, script: Dict[str, str], default_reply: str = "TRANSLATED") -> None:
        self.script = script
        self.default_reply = default_reply
        self.call_count = 0
        self.calls: List[str] = []

    def translate_once(
        self,
        text: str,
        tgt: str,
        src_lang: Optional[str],
        cancel_event: Optional[threading.Event] = None,
        system_context: Optional[str] = None,
    ) -> Tuple[bool, str]:
        self.call_count += 1
        self.calls.append(text)
        return True, self.script.get(text, self.default_reply)

    def translate_json(
        self,
        user_payload: str,
        cancel_event: Optional[threading.Event] = None,
        system_context: Optional[str] = None,
    ) -> Tuple[bool, str]:
        text = _extract_body_text(user_payload)
        self.call_count += 1
        self.calls.append(text)
        return True, json.dumps({"translation": self.script.get(text, self.default_reply)})


# ---------------------------------------------------------------------------
# AC-1: trivial/non-translatable body segments -> NOT called, output = source
# ---------------------------------------------------------------------------
class TestTrivialPassthrough:
    def test_pure_number_not_called_output_equals_source(self) -> None:
        client = FakeLLMClient(reply="SHOULD_NOT_APPEAR")
        results = translate_merged_paragraphs([PAGE_NUMBER_SEGMENT], "zh-TW", "en", client)
        assert client.call_count == 0
        assert results == [(True, PAGE_NUMBER_SEGMENT)]

    def test_punctuation_only_not_called_output_equals_source(self) -> None:
        client = FakeLLMClient(reply="SHOULD_NOT_APPEAR")
        results = translate_merged_paragraphs([PUNCTUATION_ONLY_SEGMENT], "zh-TW", "en", client)
        assert client.call_count == 0
        assert results == [(True, PUNCTUATION_ONLY_SEGMENT)]

    def test_whitespace_only_not_called_output_equals_source(self) -> None:
        client = FakeLLMClient(reply="SHOULD_NOT_APPEAR")
        results = translate_merged_paragraphs([WHITESPACE_ONLY_SEGMENT], "zh-TW", "en", client)
        assert client.call_count == 0
        assert results == [(True, WHITESPACE_ONLY_SEGMENT)]

    def test_already_target_language_token_not_called_output_equals_source(self) -> None:
        # A short alphanumeric product/lot code — the same in every target
        # language/script, and short enough that should_translate() rejects it.
        client = FakeLLMClient(reply="SHOULD_NOT_APPEAR")
        results = translate_merged_paragraphs([SHORT_LOT_SEGMENT], "zh-TW", "en", client)
        assert client.call_count == 0
        assert results == [(True, SHORT_LOT_SEGMENT)]

    def test_very_short_single_token_not_called_output_equals_source(self) -> None:
        client = FakeLLMClient(reply="SHOULD_NOT_APPEAR")
        results = translate_merged_paragraphs([SHORT_CODE_SEGMENT], "zh-TW", "en", client)
        assert client.call_count == 0
        assert results == [(True, SHORT_CODE_SEGMENT)]


# ---------------------------------------------------------------------------
# AC-2: meta/refusal reply -> discarded; SOURCE written, never the meta string
# ---------------------------------------------------------------------------
class TestRefusalOutputGuard:
    def test_ask_back_reply_source_written_not_meta_string(self) -> None:
        client = FakeLLMClient(reply=ASK_BACK_REPLY)
        results = translate_merged_paragraphs(
            [ALREADY_ENGLISH_LABEL_SEGMENT], "zh-TW", "en", client
        )
        assert client.call_count == 1
        assert results == [(True, ALREADY_ENGLISH_LABEL_SEGMENT)]
        assert ASK_BACK_REPLY not in [translated for _, translated in results]

    def test_question_back_reply_source_written_not_meta_string(self) -> None:
        reply = "What would you like me to translate?"
        client = FakeLLMClient(reply=reply)
        results = translate_merged_paragraphs(
            [ALREADY_ENGLISH_LABEL_SEGMENT], "zh-TW", "en", client
        )
        assert client.call_count == 1
        assert results == [(True, ALREADY_ENGLISH_LABEL_SEGMENT)]
        assert reply not in [translated for _, translated in results]

    def test_language_detection_note_reply_source_written_not_meta_string(self) -> None:
        reply = "I don't see any text provided for translation."
        client = FakeLLMClient(reply=reply)
        results = translate_merged_paragraphs(
            [ALREADY_ENGLISH_LABEL_SEGMENT], "zh-TW", "en", client
        )
        assert client.call_count == 1
        assert results == [(True, ALREADY_ENGLISH_LABEL_SEGMENT)]
        assert reply not in [translated for _, translated in results]

    def test_meta_refusal_inside_schema_valid_json_still_caught(self) -> None:
        """BR-108 widened by BR-112: a meta/refusal reply wrapped in
        schema-valid, non-echoed JSON (`{"translation": "..."}`) satisfies
        every BR-112 structural check yet MUST still be caught here — the
        FakeLLMClient's `translate_json` wraps `reply` in a valid envelope,
        exercising the default JSON-ON path directly (not just the
        plain-text `translate_once` path the other cases in this class use)."""
        reply = "I need more context to translate this"
        client = FakeLLMClient(reply=reply)
        results = translate_merged_paragraphs(
            [ALREADY_ENGLISH_LABEL_SEGMENT], "zh-TW", "en", client
        )
        assert client.call_count == 1
        assert results == [(True, ALREADY_ENGLISH_LABEL_SEGMENT)]
        assert reply not in [translated for _, translated in results]


# ---------------------------------------------------------------------------
# AC-3 (MANDATORY negative): genuine translation is NOT misclassified/suppressed
# ---------------------------------------------------------------------------
class TestRefusalDetectorNegative:
    def test_genuine_translation_containing_question_mark_is_not_suppressed(self) -> None:
        genuine = "這個設備已經停止運作了嗎?"
        client = FakeLLMClient(reply=genuine)
        results = translate_merged_paragraphs([CJK_SENTENCE_SEGMENT], "zh-TW", "zh-CN", client)
        assert client.call_count == 1
        assert results == [(True, genuine)]

    def test_genuine_translation_reading_like_a_note_is_not_suppressed(self) -> None:
        genuine = "Note: this describes the corrective action taken for the failure mode."
        client = FakeLLMClient(reply=genuine)
        results = translate_merged_paragraphs([CJK_SENTENCE_SEGMENT], "en", "zh-CN", client)
        assert client.call_count == 1
        assert results == [(True, genuine)]

    def test_genuine_translation_need_more_context_short_form_is_not_suppressed(self) -> None:
        """"需要更多上下文" translates verbatim to "Need more context." — an
        UNANCHORED "need more context" pattern would misclassify this
        legitimate translation as a refusal and discard it in favor of the
        (wrong-language) source. The anchored "more context to translate"
        pattern must NOT match this reply."""
        genuine = "Need more context."
        client = FakeLLMClient(reply=genuine)
        results = translate_merged_paragraphs([CJK_SENTENCE_SEGMENT], "en", "zh-CN", client)
        assert client.call_count == 1
        assert results == [(True, genuine)]

    def test_genuine_translation_need_more_context_in_a_sentence_is_not_suppressed(self) -> None:
        """A genuine, ordinary sentence that happens to contain "need more
        context" — not a self-referential ask-back about the ACT of
        translating — must survive as the translation."""
        genuine = "The reviewer will need more context."
        client = FakeLLMClient(reply=genuine)
        results = translate_merged_paragraphs([CJK_SENTENCE_SEGMENT], "en", "zh-CN", client)
        assert client.call_count == 1
        assert results == [(True, genuine)]


# ---------------------------------------------------------------------------
# AC-4: genuinely translatable content is still sent to the LLM (no over-passthrough)
# ---------------------------------------------------------------------------
class TestConservativePassthrough:
    def test_genuine_sentence_is_sent_to_client_and_translated(self) -> None:
        genuine = "Failure cause: the trimming mold scrap scratched the component body."
        client = FakeLLMClient(reply=genuine)
        results = translate_merged_paragraphs([CJK_SENTENCE_SEGMENT], "en", "zh-CN", client)
        assert client.call_count > 0
        assert results == [(True, genuine)]


# ---------------------------------------------------------------------------
# AC-1, AC-2, AC-4 combined in one translate_merged_paragraphs call
# ---------------------------------------------------------------------------
class TestTranslateMergedParagraphsEndToEnd:
    def test_trivial_and_refusal_and_normal_segments_in_one_call(self) -> None:
        genuine_translation = "Failure cause: the trimming mold scrap scratched the component body."
        script = {
            ALREADY_ENGLISH_LABEL_SEGMENT: ASK_BACK_REPLY,
            CJK_SENTENCE_SEGMENT: genuine_translation,
        }
        client = ScriptedLLMClient(script)
        texts = [
            PAGE_NUMBER_SEGMENT,  # trivial -> must NOT be sent
            ALREADY_ENGLISH_LABEL_SEGMENT,  # sent, refusal reply -> source fallback
            CJK_SENTENCE_SEGMENT,  # sent, genuine translation -> kept
        ]

        results = translate_merged_paragraphs(texts, "zh-TW", "en", client)

        assert client.call_count == 2  # only the two non-trivial segments
        assert PAGE_NUMBER_SEGMENT not in client.calls
        assert results[0] == (True, PAGE_NUMBER_SEGMENT)
        assert results[1] == (True, ALREADY_ENGLISH_LABEL_SEGMENT)
        assert results[2] == (True, genuine_translation)


# ---------------------------------------------------------------------------
# AC-6: RED-before / GREEN-after reproduction from the real 8D trivial segments
# ---------------------------------------------------------------------------
class TestReproduction8D:
    def test_8d_trivial_segment_fixture_ask_back_fake_red_pre_fix_green_post_fix(self) -> None:
        """Reproduces the 8D PDF bug (task 42265c0b): a trivial/already-English
        body segment gets a live meta/refusal reply written verbatim into output.

        Pre-fix (RED): neither guard exists. Both segments below are sent to the
        LLM (no BR-107 input guard) and the ask-back reply is stored verbatim as
        the "translation" for both (no BR-108 output guard) — every assertion
        below fails against pre-fix code.

        Post-fix (GREEN): the lone page number never reaches the client (BR-107
        input guard); the already-English label IS sent, receives the ask-back
        reply, and the BR-108 output guard discards it in favor of the source.
        No live LLM is used anywhere in this test.
        """
        client = FakeLLMClient(reply=ASK_BACK_REPLY)
        texts = [PAGE_NUMBER_SEGMENT, ALREADY_ENGLISH_LABEL_SEGMENT]

        results = translate_merged_paragraphs(texts, "zh-TW", "en", client)

        # BR-107: trivial page-number segment never reaches the LLM.
        assert client.call_count == 1
        assert results[0] == (True, PAGE_NUMBER_SEGMENT)

        # BR-108: the already-English label is sent, but the ask-back reply is
        # discarded in favor of the source — the meta string must never appear.
        assert results[1] == (True, ALREADY_ENGLISH_LABEL_SEGMENT)
        assert ASK_BACK_REPLY not in (results[0][1], results[1][1])


# ---------------------------------------------------------------------------
# Bonus: direct unit coverage of the new pure helper (beyond the AC node IDs)
# ---------------------------------------------------------------------------
class TestIsMetaRefusalHelperDirect:
    def test_short_ask_back_reply_is_detected(self) -> None:
        assert is_meta_refusal(ASK_BACK_REPLY, ALREADY_ENGLISH_LABEL_SEGMENT) is True

    def test_long_genuine_translation_is_not_detected_length_gate(self) -> None:
        # Exceeds META_REFUSAL_MAX_CHARS (200) — the length-gate false-positive guard.
        genuine = "A" * 250
        assert is_meta_refusal(genuine, CJK_SENTENCE_SEGMENT) is False

    def test_empty_reply_is_not_a_refusal(self) -> None:
        assert is_meta_refusal("", CJK_SENTENCE_SEGMENT) is False

    def test_br108_json_example_is_detected(self) -> None:
        """The exact meta-refusal example quoted in business-rules.md BR-108
        (`{"translation": "I need more context to translate this"}`) must be
        caught — the anchored "i need more context to translate" pattern."""
        assert is_meta_refusal("I need more context to translate this", "制作日期") is True

    def test_translation_domain_prose_is_not_a_refusal(self) -> None:
        """A document ABOUT translation can legitimately contain the phrase
        "more context to translate". A meta-refusal is always the model speaking
        about ITSELF, so the pattern is anchored on the first-person frame.

        Both strings below are correct translations, not ask-backs. Before the
        anchor was added they were suppressed and replaced by their source —
        BR-108's precision mandate forbids exactly that.
        """
        assert is_meta_refusal(
            "The translator needs more context to translate this document.",
            "譯者需要更多上下文才能翻譯這份文件",
        ) is False
        assert is_meta_refusal(
            "Please provide more context to translate the remaining terms.",
            "請提供更多上下文以便翻譯其餘術語",
        ) is False

    def test_need_more_context_short_form_is_not_a_refusal(self) -> None:
        """"Need more context." is a genuine, correct translation (of e.g.
        Chinese "需要更多上下文") — NOT a self-referential ask-back — and
        must NOT be classified as a refusal."""
        assert is_meta_refusal("Need more context.", "需要更多上下文") is False

    def test_need_more_context_in_ordinary_sentence_is_not_a_refusal(self) -> None:
        """An ordinary sentence containing "need more context" that is not
        about the act of translating must NOT be classified as a refusal."""
        assert is_meta_refusal("The reviewer will need more context.", "審查者需要更多背景") is False
