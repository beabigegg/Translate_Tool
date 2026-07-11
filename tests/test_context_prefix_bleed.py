"""RED/GREEN reproduction test for context-prefix-bleed-fix.

Real 8D 3-point fixture segments below are copied verbatim from
change-request.md (source PDF: docs/TEST_DOC/CS2408-0021 ... P6SMBJ18CA ...).

Root cause (pre-fix): `build_context_prefix` (BR-78) returns a
"Context (do not translate):\n<prev 2 raw segments>\n\n" block, and
`translate_merged_paragraphs` glues that block onto the segment text
BEFORE handing it to `client.translate_once`. The cloud client wraps the
whole thing as "Translate the following text...\n\n<glued text>", so a
provider that translates literally whatever is in the user payload (PANJIT/
DeepSeek) bleeds the preceding segments' text into segment N's output.

Fix: route context via `translate_once(system_context=...)` — a dedicated,
non-translatable channel — instead of concatenating it onto the user text.

Mock boundary: the `LLMClient` Protocol seam (`translate_once`), not HTTP —
the bug is prompt assembly, not transport. The fake client "translates"
by echoing exactly the `text` it receives, standing in for a provider that
translates whatever sits in the user message; it records `system_context`
separately so tests can assert WHICH channel carried which text.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from app.backend import config
from app.backend.services.context_prompts import build_context_prefix
from app.backend.utils.translation_helpers import translate_merged_paragraphs

# Real 8D fixture segments (verbatim from change-request.md).
SEG1 = "1、客户信和达（欧朗）2024.08.23反馈我司材料P6SMBJ18CA DC 2427M 20PCS本体破损，退回4pcs分析"
SEG2 = "2、不良品本体侧面破损，破损处有锡电镀层，判断为电镀前本体打伤"
SEG3 = (
    "3、此失效模式内部外检有发现，分析此次失小影响因子为："
    "A.焊接后 Clip偏位or分离落在料片上而残留在弯脚模具卡料导致切伤材料本体；"
    "B.成型未灌满脚架切片卡料，C.弯脚机台上有吸气装置"
)


class _FakeEchoClient:
    """Fake LLMClient that "translates" by echoing exactly the user `text`.

    Stands in for PANJIT/DeepSeek's behavior of translating literally
    whatever is inside the user payload. Records `system_context`
    separately (per call) so tests can assert WHICH text landed in WHICH
    channel — an anti-tautology selection assertion, not a count/length one.

    cloud-reasoning-stall-hardening (BR-118/ADR-0021): mirrors
    `OpenAICompatibleClient._post_completion`'s composition by prepending the
    harmony `Reasoning: <level>` directive (sourced from
    `config.OPENAI_TRANSLATION_REASONING`) to the recorded `system_context`,
    the SAME way the real client does ahead of the base prompt / neighbor
    context — so this fixture continues to exercise the real no-leak
    invariant now that a directive is composed into the system channel.
    """

    def __init__(self) -> None:
        self.calls: List[dict] = []

    def translate_once(
        self,
        text: str,
        tgt: str,
        src_lang: Optional[str],
        cancel_event=None,
        system_context: Optional[str] = None,
    ) -> Tuple[bool, str]:
        directive = f"Reasoning: {config.OPENAI_TRANSLATION_REASONING}"
        merged_system_context = (
            f"{directive}\n\n{system_context}" if system_context else directive
        )
        self.calls.append({"text": text, "system_context": merged_system_context})
        return True, text  # echo: whatever is in `text` is what gets "translated"

    def translate_batch(self, texts, tgt, src_lang):
        return True, list(texts)

    def health(self):
        return True, "ok"

    def list_models(self):
        return []

    def unload(self):
        return True, "no-op"


def _run_fixture(monkeypatch):
    monkeypatch.setattr(config, "CONTEXT_WINDOW_SEGMENTS", 2)
    monkeypatch.setattr(config, "CONTEXT_MAX_CHARS", 300)
    # json-structured-translation-io: this fixture's `_FakeEchoClient` echoes
    # the exact source text back as the "translation" — under the JSON-ON
    # default that is BY DEFINITION an echoed-source reply (BR-112), which
    # would trigger the plain-text fallback and double-record each call. This
    # test's actual subject (BR-78 system_context routing) is orthogonal to
    # the wire-format flag, so it is pinned to the plain-text `translate_once`
    # path it was written against.
    monkeypatch.setattr(config, "JSON_STRUCTURED_TRANSLATION_ENABLED", False)
    client = _FakeEchoClient()
    results = translate_merged_paragraphs([SEG1, SEG2, SEG3], "vi", "zh-CN", client)
    return client, results


# ---------------------------------------------------------------------------
# AC-1
# ---------------------------------------------------------------------------

def test_build_context_prefix_returns_system_channel_block_no_user_glue() -> None:
    """build_context_prefix returns a system-channel reference block, not the
    old user-glue "Context (do not translate):" framing."""
    result = build_context_prefix([SEG1, SEG2, SEG3], current_idx=2, n_context=2, max_chars=300)
    assert "Context (do not translate):" not in result
    assert SEG1 in result
    assert SEG2 in result


def test_translate_merged_paragraphs_user_payload_excludes_neighbor_segments(monkeypatch) -> None:
    """The `text=` handed to translate_once for segment N excludes verbatim
    neighbor segments N-1/N-2 (selection assertion: WHICH text, not a count)."""
    client, _ = _run_fixture(monkeypatch)
    seg3_call = client.calls[2]
    assert seg3_call["text"] == SEG3
    assert SEG1 not in seg3_call["text"]
    assert SEG2 not in seg3_call["text"]


# ---------------------------------------------------------------------------
# AC-2 / AC-3 (RED pre-fix / GREEN post-fix — same node per bug-fix-lane rule)
# ---------------------------------------------------------------------------

def test_fake_client_no_bleed_returns_only_target_segment_8d_fixture(monkeypatch) -> None:
    """A fake client that "translates whatever it is asked to translate"
    returns ONLY segment 3's own text — no bleed of points 1/2 — using the
    real 8D 3-point fixture."""
    _, results = _run_fixture(monkeypatch)
    ok, translated = results[2]
    assert ok is True
    assert translated == SEG3
    assert SEG1 not in translated
    assert SEG2 not in translated


# ---------------------------------------------------------------------------
# AC-4
# ---------------------------------------------------------------------------

def test_neighbor_text_appears_only_in_system_context_never_in_translated_output(monkeypatch) -> None:
    """Neighbor text appears ONLY in the captured system_context, never in
    the text handed for translation nor in the translated output."""
    client, results = _run_fixture(monkeypatch)
    seg3_call = client.calls[2]
    assert seg3_call["system_context"] is not None
    assert SEG1 in seg3_call["system_context"]
    assert SEG2 in seg3_call["system_context"]

    _, seg3_translated = results[2]
    assert SEG1 not in seg3_translated
    assert SEG2 not in seg3_translated


# ---------------------------------------------------------------------------
# AC-5 — BR-78: context delivered out-of-band, never in the translatable payload
# ---------------------------------------------------------------------------

def test_br78_context_delivered_out_of_band_not_in_translatable_payload(monkeypatch) -> None:
    """For every call, the translatable `text=` payload contains ONLY that
    segment's own source text — never a sibling segment's verbatim text."""
    client, _ = _run_fixture(monkeypatch)
    all_texts = {SEG1, SEG2, SEG3}
    for call in client.calls:
        siblings = all_texts - {call["text"]}
        for sibling in siblings:
            assert sibling not in call["text"], (
                f"Sibling segment text leaked into translatable payload: {call['text']!r}"
            )


# ---------------------------------------------------------------------------
# AC-6 — no config value change
# ---------------------------------------------------------------------------

def test_context_window_segments_and_max_chars_constants_unchanged() -> None:
    """CONTEXT_WINDOW_SEGMENTS (2) and CONTEXT_MAX_CHARS (300) retain their
    existing values — this fix relocates context delivery, it does not
    change the window/cap configuration."""
    assert config.CONTEXT_WINDOW_SEGMENTS == 2
    assert config.CONTEXT_MAX_CHARS == 300


# ---------------------------------------------------------------------------
# cloud-reasoning-stall-hardening (BR-118/ADR-0021) — Reasoning directive
# no-leak extension: the directive is EXPECTED in the system channel, and
# must still never appear in any user-role `text=` payload.
# ---------------------------------------------------------------------------

def test_reasoning_directive_present_in_system_context_never_in_user_text(monkeypatch) -> None:
    """The `Reasoning: <level>` directive (BR-118) is present in every call's
    system_context (composed the way the real client composes it) and is
    absent from every call's translatable `text=` payload — an EXPECTED
    presence-in-system / absence-in-user update, not a regression."""
    client, results = _run_fixture(monkeypatch)
    directive = f"Reasoning: {config.OPENAI_TRANSLATION_REASONING}"

    assert client.calls, "fixture must produce at least one call"
    for call in client.calls:
        assert directive in call["system_context"], (
            "Reasoning directive must be present in the system channel"
        )
        assert directive not in call["text"], (
            "Reasoning directive must NEVER leak into the translatable user payload"
        )

    for ok, translated in results:
        assert ok is True
        assert directive not in translated
