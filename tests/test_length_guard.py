"""TDD tests for truncation-length-guard (BR-117, ADR-0020, truncation-length-guard).

Covers:
  - AC-1: the composition length model flags the recorded 4827->370 bug ratio.
  - AC-2: a flagged cell is routed into recovery and the WRITTEN final_tmap
    value is the recovered (or longer-of-the-two) translation, never source.
  - AC-3: zero false positives on legitimate-short calibration fixtures
    (CJK-heavy AND latin-heavy) at k=0.3 — the load-bearing FP boundary.
  - AC-4: fail-safe (no flag) on an uncalibrated target, a short source, and
    E == 0 (numeric) — each independently.
  - AC-5: BR-68 numeric cells never reach a flagged state (E == 0 backstop).
  - AC-6: recovery is bounded to exactly one attempt, never re-enters the
    guard, and keeps the LONGEST of {accepted, recovered} — never source,
    never the BR-25 placeholder.
  - AC-7: a plausible-length reply is accepted unchanged: no recovery call,
    no WARNING.
  - AC-8: the composition model excludes digits/punctuation/whitespace.

Anti-tautology rules (CLAUDE.md):
  - Integration assertions read the WRITTEN `final_tmap` value passed to
    `_insert_docx_translations` (the real acceptance-write boundary), never
    just call-wiring/counts alone.
  - WARNING/no-WARNING assertions filter `record.name == "TranslateTool"`
    (caplog attaches to root; a bare check would silently pass on any logger).
  - Recovery-bounded assertions count the EXACT number of `translate_texts`
    calls and the EXACT number of `is_suspiciously_short` calls (guards
    against a hidden re-entrant loop), not just "recovery happened".

Collection-time imports: `_docx_proc` is captured at collection time so
`patch.object` is immune to sys.modules contamination (CLAUDE.md promoted
learnings).
"""

from __future__ import annotations

import json
import logging
import math
import random
from unittest.mock import MagicMock, patch

import docx
import pytest

from app.backend import config
import app.backend.processors.docx_processor as _docx_proc
from app.backend.utils.length_guard import expected_length, is_suspiciously_short
from app.backend.utils.text_utils import count_composition, normalize_text

# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

# Mirrors the design.md hazard: a merged "layout" table cell holding several
# paragraphs of a document section, joined with "\n" (BR-82's split unit).
CELL_LINES = [
    "系統版本編號與相關文件說明內容",
    "測試環境設定與參數調整說明文字",
    "產品規格書內容摘要與注意事項",
]
CELL_TEXT = "\n".join(CELL_LINES)

TARGET = "Vietnamese"


def _make_client_mock(**kwargs) -> MagicMock:
    m = MagicMock()
    m.health_check.return_value = (True, "ok")
    m.system_prompt = ""
    m.model_type = "general"
    m._is_translation_dedicated.return_value = False
    m._is_translategemma_model.return_value = False
    for k, v in kwargs.items():
        setattr(m, k, v)
    return m


def _make_docx_with_one_cell(tmp_path, cell_text: str):
    doc = docx.Document()
    t = doc.add_table(rows=1, cols=1)
    t.cell(0, 0).text = cell_text
    in_path = tmp_path / "in.docx"
    doc.save(str(in_path))
    return in_path


def _json_cell_reply(translation: str) -> str:
    return json.dumps({"cells": [{"row": 0, "col": 0, "translation": translation}]})


def _run_translate_docx_capture(tmp_path, cell_text, client, translate_texts_double, monkeypatch):
    """Run translate_docx over a 1x1-table docx holding `cell_text`, patching
    `translate_texts` (the recovery seam's only LLM call) and capturing the
    `final_tmap` dict passed to `_insert_docx_translations` (the acceptance
    WRITE boundary). Returns (final_tmap, translate_texts_mock, guard_mock,
    recovery_calls) where `recovery_calls` is the subset of `translate_texts`
    calls with a NON-empty `texts` argument — the fixture docx has a single
    table cell and no body paragraphs, so `translate_texts` is still called
    once, unconditionally, with an EMPTY list for the (absent) body path
    (docx_processor.py's para_tmap build); that call is not a recovery call.
    """
    monkeypatch.setattr(config, "JSON_STRUCTURED_TRANSLATION_ENABLED", True)
    in_path = _make_docx_with_one_cell(tmp_path, cell_text)
    out_path = tmp_path / "out.docx"

    real_guard = is_suspiciously_short
    with patch.object(_docx_proc, "translate_texts", side_effect=translate_texts_double) as tt_mock, \
         patch.object(_docx_proc, "is_suspiciously_short", wraps=real_guard) as guard_mock, \
         patch.object(_docx_proc, "_insert_docx_translations") as insert_mock:
        _docx_proc.translate_docx(
            str(in_path), str(out_path),
            targets=[TARGET], src_lang="zh",
            client=client,
            include_headers_shapes_via_com=False,
        )

    assert insert_mock.call_count == 1, "expected exactly one _insert_docx_translations call"
    final_tmap = insert_mock.call_args[0][2]
    recovery_calls = [c for c in tt_mock.call_args_list if c.args[0]]
    return final_tmap, tt_mock, guard_mock, recovery_calls


# ---------------------------------------------------------------------------
# AC-1 / AC-8: pure composition length model
# ---------------------------------------------------------------------------

class TestPureCompositionModel:
    def test_flags_recorded_bug_ratio(self):
        """The recorded 4827->370 bug (ratio 0.077 in ADR-0020) must flag at
        k=0.3 for a calibrated (Vietnamese) target. Falsifiability: hardcoding
        is_suspiciously_short() to always return False, or reversing the
        `translated_len < k*E` comparison, turns this RED."""
        source = "測" * 4827
        translation = "字" * 370
        assert is_suspiciously_short(source, translation, "Vietnamese") is True

    def test_mixed_composition_excludes_numeric(self):
        """AC-8: digits, punctuation, and whitespace are excluded from the
        composition count (BR-68); only CJK and non-CJK alphabetic characters
        contribute to `E`."""
        source = "版本編號 12345 -- ABC"
        norm = normalize_text(source)
        cjk, latin = count_composition(norm)
        assert (cjk, latin) == (4, 3), (
            f"expected 4 CJK chars (版本編號) and 3 latin-alpha chars (ABC), "
            f"digits/punct/whitespace excluded; got cjk={cjk} latin={latin}"
        )
        e = expected_length(norm, "Vietnamese", config.TRUNCATION_GUARD_COEFFICIENTS)
        assert e == pytest.approx(3.51 * 4 + 0.75 * 3)


# ---------------------------------------------------------------------------
# AC-3: zero false positives — the load-bearing FP boundary
# ---------------------------------------------------------------------------

class TestZeroFalsePositives:
    LEGIT_SHORT_PAIRS = [
        pytest.param(
            "系統版本編號系統版本編號系統版本編號",
            "Phiên bản hệ thống và số hiệu sản phẩm được cập nhật",
            id="cjk-heavy-1",
        ),
        pytest.param(
            "產品規格說明文件內容摘要總覽表",
            "Tóm tắt tổng quan nội dung tài liệu mô tả thông số kỹ thuật sản phẩm",
            id="cjk-heavy-2",
        ),
        pytest.param(
            "This is a legitimate short technical specification line for review",
            "Đây là dòng ngắn hợp lệ",
            id="latin-heavy-1",
        ),
        pytest.param(
            "Please confirm the delivery schedule and update accordingly today",
            "Vui lòng xác nhận và cập nhật lịch giao hàng",
            id="latin-heavy-2",
        ),
    ]

    @pytest.mark.parametrize("source,translation", LEGIT_SHORT_PAIRS)
    def test_zero_false_positives_calibration_fixtures(self, source, translation):
        """Zero flags across CJK-heavy AND latin-heavy legitimate-short pairs
        at k=0.3. A false positive here re-translates a CORRECT output —
        worse than the bug (design.md's user-stated hazard)."""
        assert config.TRUNCATION_GUARD_K == 0.3, "test assumes the documented k"
        assert is_suspiciously_short(source, translation, "Vietnamese") is False


# ---------------------------------------------------------------------------
# AC-4: fail-safe early returns (each independent — Falsifiability anchors)
# ---------------------------------------------------------------------------

class TestFailSafe:
    def test_failsafe_unknown_target(self):
        """An uncalibrated target must never flag, regardless of how short
        the translation is. Falsifiability: removing this early-return turns
        this RED (it would flag)."""
        source = "測" * 4827
        translation = "字" * 5
        assert is_suspiciously_short(source, translation, "Klingon") is False

    def test_failsafe_short_source_below_min_chars(self):
        """A normalized source shorter than MIN_SOURCE_CHARS (15) must never
        flag. Falsifiability: removing this early-return turns this RED."""
        assert config.TRUNCATION_GUARD_MIN_SOURCE_CHARS == 15
        short_source = "短" * 10
        assert len(normalize_text(short_source)) < 15
        assert is_suspiciously_short(short_source, "x", "Vietnamese") is False

    def test_failsafe_zero_expected_length_numeric_source(self):
        """An all-numeric source (E == 0, BR-68 backstop) must never flag.
        Falsifiability: removing this early-return turns this RED."""
        numeric_source = "12,345.67 / 89-0123456"
        assert len(normalize_text(numeric_source)) >= 15
        cjk, latin = count_composition(normalize_text(numeric_source))
        assert (cjk, latin) == (0, 0)
        assert is_suspiciously_short(numeric_source, "x", "Vietnamese") is False


# ---------------------------------------------------------------------------
# AC-5: BR-68 numeric cells never reach a flagged state
# ---------------------------------------------------------------------------

class TestNumericCellNeverFlagged:
    def test_numeric_cell_never_reaches_guard(self):
        """A BR-68 numeric cell (digits + common separators only) is excluded
        from the JSON-path content_cells filter entirely (is_numeric_cell);
        the guard's E==0 backstop independently ensures it is never flagged
        even if it slipped through."""
        from app.backend.utils.text_utils import is_numeric_cell

        numeric_source = "1,234,567.89"
        assert is_numeric_cell(numeric_source) is True
        assert is_suspiciously_short(numeric_source, "", "Vietnamese") is False


# ---------------------------------------------------------------------------
# AC-2 / AC-6: recovery integration at the DOCX cell-acceptance seam
# ---------------------------------------------------------------------------

class TestRecoveryIntegration:
    def test_cell_seam_flags_and_recovers_truncated_reply(self, tmp_path, monkeypatch):
        """A whole-table JSON reply that is suspiciously short routes into
        `_recover_truncated_cell`; the WRITTEN final_tmap value is the
        recovered reassembly (better/longer than the truncated accepted
        reply), and is NEVER the source text nor a BR-25 placeholder."""
        short_translation = "Nội dung ngắn"
        recovered_lines = [
            "Số phiên bản hệ thống và tài liệu liên quan được mô tả chi tiết ở đây",
            "Thiết lập môi trường thử nghiệm và điều chỉnh tham số được giải thích rõ ràng",
            "Tóm tắt nội dung quy cách sản phẩm và các lưu ý quan trọng cần biết",
        ]
        assert is_suspiciously_short(CELL_TEXT, short_translation, TARGET) is True

        client = _make_client_mock()
        client.translate_json.return_value = (True, _json_cell_reply(short_translation))

        def fake_translate_texts(texts, targets, src_lang, client, **kwargs):
            if not texts:
                return {}, 0, 0, False  # unconditional (empty) body-path call, not a recovery call
            tgt = targets[0]
            tmap = {(tgt, line): recovered for line, recovered in zip(texts, recovered_lines)}
            return tmap, len(texts), 0, False

        final_tmap, tt_mock, guard_mock, recovery_calls = _run_translate_docx_capture(
            tmp_path, CELL_TEXT, client, fake_translate_texts, monkeypatch
        )

        kept = final_tmap[(TARGET, CELL_TEXT, 0)]
        assert kept == "\n".join(recovered_lines), (
            "expected the recovered reassembly (longer than the truncated "
            "accepted reply) to be written"
        )
        assert kept != CELL_TEXT, "must never write the source text"
        assert not kept.startswith("[Translation failed|"), "must never write the BR-25 placeholder"
        assert len(recovery_calls) == 1, "recovery must call translate_texts exactly once"

    def test_recovery_bounded_single_attempt_no_reentry(self, tmp_path, monkeypatch):
        """AC-6: recovery is a single straight-line call — exactly one
        translate_texts call, and the guard (is_suspiciously_short) is
        called exactly once per cell (never re-invoked on the recovered
        output, i.e. no re-entrant loop). Falsifiability: an unbounded
        retry loop, or a re-entrant guard check on the recovered value,
        would surface as call_count > 1 on either mock."""
        short_translation = "Nội dung ngắn"
        recovered_lines = ["A recovered line one here", "A recovered line two here", "A recovered line three"]

        client = _make_client_mock()
        client.translate_json.return_value = (True, _json_cell_reply(short_translation))

        def fake_translate_texts(texts, targets, src_lang, client, **kwargs):
            if not texts:
                return {}, 0, 0, False  # unconditional (empty) body-path call, not a recovery call
            tgt = targets[0]
            tmap = {(tgt, line): recovered for line, recovered in zip(texts, recovered_lines)}
            return tmap, len(texts), 0, False

        _final_tmap, tt_mock, guard_mock, recovery_calls = _run_translate_docx_capture(
            tmp_path, CELL_TEXT, client, fake_translate_texts, monkeypatch
        )

        assert len(recovery_calls) == 1, (
            f"expected exactly one recovery translate_texts() call, got {len(recovery_calls)}"
        )
        assert guard_mock.call_count == 1, (
            f"expected the guard to run exactly once (the single accepted cell), "
            f"not re-invoked on the recovered value; got {guard_mock.call_count}"
        )

    def test_recovery_keeps_longest_on_exhaustion_never_source(self, tmp_path, monkeypatch):
        """On exhaustion (recovered reassembly ends up SHORTER than the
        original accepted reply), the LONGEST of {accepted, recovered} is
        kept — never source, never the BR-25 placeholder. Falsifiability:
        changing keep-longest to keep-source turns this RED (kept would
        equal CELL_TEXT); changing it to always-keep-recovered turns this
        RED too (kept would equal the shorter recovered value)."""
        accepted = "Bản dịch ngắn nhưng vẫn dài hơn"  # still flagged, but longer than recovery below
        assert is_suspiciously_short(CELL_TEXT, accepted, TARGET) is True
        poor_recovered_lines = ["A", "B", "C"]
        assert len("\n".join(poor_recovered_lines)) < len(accepted)

        client = _make_client_mock()
        client.translate_json.return_value = (True, _json_cell_reply(accepted))

        def fake_translate_texts(texts, targets, src_lang, client, **kwargs):
            if not texts:
                return {}, 0, 0, False  # unconditional (empty) body-path call, not a recovery call
            tgt = targets[0]
            tmap = {(tgt, line): recovered for line, recovered in zip(texts, poor_recovered_lines)}
            return tmap, len(texts), 0, False

        final_tmap, tt_mock, guard_mock, recovery_calls = _run_translate_docx_capture(
            tmp_path, CELL_TEXT, client, fake_translate_texts, monkeypatch
        )

        kept = final_tmap[(TARGET, CELL_TEXT, 0)]
        assert kept == accepted, "expected the longer (accepted) attempt to be kept on exhaustion"
        assert len(recovery_calls) == 1, "recovery must call translate_texts exactly once"
        assert kept != CELL_TEXT, "must never write the source text"
        assert not kept.startswith("[Translation failed|"), "must never write the BR-25 placeholder"


# ---------------------------------------------------------------------------
# AC-7: normal-length reply unaffected — no recovery, no WARNING
# ---------------------------------------------------------------------------

class TestNormalReplyUnaffected:
    def test_normal_length_reply_unaffected_no_recovery_no_warning(self, tmp_path, monkeypatch, caplog):
        """A plausible-length reply must be accepted unchanged: no recovery
        call fires, and no truncation-guard WARNING is logged on the
        TranslateTool logger. Falsifiability: any change that fires recovery
        or the WARNING for this reply turns this RED."""
        normal_translation = (
            "Đây là bản dịch đầy đủ và hợp lý cho toàn bộ nội dung của ô bảng "
            "này, không bị cắt ngắn"
        )
        assert is_suspiciously_short(CELL_TEXT, normal_translation, TARGET) is False

        client = _make_client_mock()
        client.translate_json.return_value = (True, _json_cell_reply(normal_translation))

        def fake_translate_texts(texts, targets, src_lang, client, **kwargs):
            if not texts:
                return {}, 0, 0, False  # unconditional (empty) body-path call, not a recovery call
            raise AssertionError("recovery must not be called for a normal-length reply")

        with caplog.at_level(logging.WARNING, logger="TranslateTool"):
            final_tmap, tt_mock, guard_mock, recovery_calls = _run_translate_docx_capture(
                tmp_path, CELL_TEXT, client, fake_translate_texts, monkeypatch
            )

        assert recovery_calls == [], "recovery must not be called"
        kept = final_tmap[(TARGET, CELL_TEXT, 0)]
        assert kept == normal_translation

        truncation_warnings = [
            r for r in caplog.records
            if r.name == "TranslateTool" and "truncation-guard" in r.getMessage()
        ]
        assert truncation_warnings == [], "must not emit a truncation-guard WARNING for a normal reply"


# =============================================================================
# Monkey / adversarial tests (monkey-test-engineer, IP-7)
# =============================================================================
# Scope: probe the FALSE-POSITIVE boundary of is_suspiciously_short() with
# adversarial-but-LEGITIMATE short translations, plus the fail-safe and
# degenerate/unicode edges. Extends this file (not a new tests/ file) per
# implementation-plan.md IP-7 / test-plan.md ("owned by monkey-test-engineer,
# referenced only") — this file is already in the change's Allowed Paths, so
# no Context Expansion Request is needed.
#
# Every case below maps to a NAMED failure mode (not random fuzzing except the
# explicitly-seeded TestSeededPropertyFuzz class, whose seeds are recorded for
# replay). See specs/changes/truncation-length-guard/monkey-test-report.md for
# the full scenario -> expected -> result table and the one BLOCKING finding
# (TestFPBoundaryExtremeCompression, xfail(strict=True) below).
# =============================================================================


class TestFPBoundaryRealisticLegitShort:
    """Realistic legitimate-short translations landing at roughly 30-46% of
    E — the practical safety margin the k=0.3 design intends (design.md D2:
    "0% FP ... every tested k up to 0.5"). Each of these is a complete,
    correct short translation of a moderately long CJK-dominant cell
    (heading / unit-symbol / acronym-cert-reference / code-copy-through).
    None must flag: a false positive here re-translates a CORRECT output."""

    REALISTIC_LEGIT_SHORT = [
        pytest.param(
            "國際標準化組織品質管理系統認證編號依照國際規範制定完成之文件",
            "Chứng nhận ISO 9001:2015 QMS đầy đủ",
            id="iso-cert-acronym-ratio-0.33",
        ),
        pytest.param(
            "系統安裝設定與操作程序完整說明文件內容摘要總覽章節",
            "Hướng dẫn cài đặt và cấu hình hệ thống",
            id="heading-ratio-0.43",
        ),
        pytest.param(
            "測試環境溫度濕度氣壓等各項參數量測單位標準符號說明",
            "Đơn vị đo nhiệt độ độ ẩm áp suất",
            id="unit-symbol-cell-ratio-0.36",
        ),
        pytest.param(
            "本產品型號代碼名稱為工業用零組件編號規格版本標示如下",
            "Mã sản phẩm ABC-999-XYZ phiên bản mới nhất",
            id="code-copy-through-ratio-0.46",
        ),
    ]

    @pytest.mark.parametrize("source,translation", REALISTIC_LEGIT_SHORT)
    def test_realistic_legit_short_not_flagged(self, source, translation):
        assert is_suspiciously_short(source, translation, "Vietnamese") is False


class TestFPBoundaryExtremeCompression:
    """ADVERSARIAL FINDING (see monkey-test-report.md — BLOCKING): an
    extreme-compression 'long descriptive CJK phrase -> bare Latin acronym'
    translation (precisely the "acronym expansion that shrinks" scenario the
    monkey-test brief names) IS flagged by the current k=0.3 / a=3.51 model.
    Observed ratio: len(translation)/E = 8/73.71 = 0.109, well below k=0.3,
    even though "ISO 9001" is a complete, correct rendering of the source
    concept.

    xfail(strict=True): if a future calibration change (e.g. an absolute
    minimum-length floor, or a lower coefficient for label/code-like cells)
    makes this XPASS, that is the intended signal to update/un-xfail this
    test and close the finding — do not silently leave it xfail-ing after a
    fix lands.
    """

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "genuine FP-boundary gap: bare-acronym compression below ~15% "
            "of E is flagged even though it is a complete, correct "
            "translation; tracked in monkey-test-report.md as a BLOCKING "
            "finding, contained (not fixed) by keep-longest/never-source/"
            "bounded-1-attempt recovery"
        ),
    )
    def test_extreme_acronym_shrink_currently_flagged_tracked_gap(self):
        source = "國際標準化組織認證品質管理系統流程規範文件"
        translation = "ISO 9001"
        assert is_suspiciously_short(source, translation, "Vietnamese") is False


class TestExactBoundaryComparison:
    def test_strict_less_than_not_less_or_equal(self):
        """The flag comparison is `translated_len < k*E`, strictly
        less-than. A translation whose length lands exactly at
        floor(k*E) (still strictly below the real-valued threshold) must
        flag; the very next integer length (now > threshold) must not.
        Falsifiability: swapping `<` for `<=` would flip behavior at an
        integer-valued threshold; this fixture is constructed so the
        threshold is non-integer, making the two sides of the comparison
        unambiguous regardless."""
        source = "測" * 20
        norm = normalize_text(source)
        e = expected_length(norm, "Vietnamese", config.TRUNCATION_GUARD_COEFFICIENTS)
        threshold = config.TRUNCATION_GUARD_K * e
        assert threshold != int(threshold), "fixture assumes a non-integer threshold"

        just_below = "x" * math.floor(threshold)
        just_above = "x" * (math.floor(threshold) + 1)
        assert len(just_below) < threshold
        assert len(just_above) > threshold
        assert is_suspiciously_short(source, just_below, "Vietnamese") is True
        assert is_suspiciously_short(source, just_above, "Vietnamese") is False


class TestFailSafeAdversarialBoundaries:
    def test_source_length_boundary_one_char_either_side(self):
        """Source normalized length exactly one char below vs. exactly at
        MIN_SOURCE_CHARS: below must fail-safe regardless of translation
        length; at the floor the guard is genuinely active (a 1-char
        translation of a 15-CJK-char source IS a real flag, not another
        fail-safe)."""
        min_chars = config.TRUNCATION_GUARD_MIN_SOURCE_CHARS
        src_below = "測" * (min_chars - 1)
        src_at = "測" * min_chars
        assert is_suspiciously_short(src_below, "x", "Vietnamese") is False
        assert is_suspiciously_short(src_at, "x", "Vietnamese") is True

    @pytest.mark.parametrize("source", [
        pytest.param("1234567890123456", id="all-digits"),
        pytest.param("!@#$%^&*()_+-=[]", id="all-punctuation"),
        pytest.param("123-456-789 / 000.111", id="digits-and-separators"),
        pytest.param("　" * 20, id="fullwidth-space-only"),
    ])
    def test_e_zero_fail_safe_regardless_of_translation_length(self, source):
        """BR-68 backstop: a normalized source with zero CJK/latin-alpha
        chars (E == 0) must never flag, even for a 1-char translation of a
        source that clears MIN_SOURCE_CHARS."""
        assert is_suspiciously_short(source, "x", "Vietnamese") is False

    @pytest.mark.parametrize("target", [
        pytest.param("French", id="uncalibrated-french"),
        pytest.param("English", id="uncalibrated-english"),
        pytest.param("", id="empty-string-target"),
        pytest.param(None, id="none-target"),
        pytest.param("vi-VN", id="code-form-not-in-table"),
        pytest.param("Klingon", id="fictional-target"),
    ])
    def test_uncalibrated_target_never_flags_real_long_source(self, target):
        """Any uncalibrated target representation must fail-safe against
        the recorded 4827-char real bug source paired with a genuinely
        very short (5-char) translation that WOULD flag under a calibrated
        (Vietnamese) target."""
        source = "測" * 4827
        translation = "字" * 5
        assert is_suspiciously_short(source, translation, target) is False

    @pytest.mark.parametrize("target", [
        "Vietnamese", "vietnamese", "VIETNAMESE", " Vietnamese ", "VietNamese",
    ])
    def test_target_key_normalization_is_case_and_whitespace_tolerant(self, target):
        """Opposite-direction risk flagged in implementation-plan.md's IP-3
        note: a case/whitespace variant of the live target string must
        still MATCH the coefficient table key, or the guard silently goes
        inert (never flags real truncation). Confirms normalization does
        not accidentally widen the fail-safe by missing a legitimate
        variant of the calibrated target."""
        source = "測" * 4827
        truncated_reply = "字" * 370  # the recorded 4827->370 bug ratio
        assert is_suspiciously_short(source, truncated_reply, target) is True


class TestDegenerateInputs:
    def test_empty_translation_of_long_source_flags_true_positive(self):
        """An empty translation of a genuinely long source is the exact
        truncation-hazard shape this guard exists to catch -- MUST flag.
        Not a false positive: this is the true positive the change exists
        for."""
        source = "測" * 4827
        assert is_suspiciously_short(source, "", "Vietnamese") is True

    def test_empty_source_fails_safe(self):
        assert is_suspiciously_short("", "some real translation text", "Vietnamese") is False

    def test_whitespace_only_source_fails_safe(self):
        assert is_suspiciously_short("     ", "x", "Vietnamese") is False

    def test_whitespace_only_translation_of_real_source_flags(self):
        """A whitespace-only 'translation' of a genuine 20-char CJK source
        is degenerate content, not a legitimate short translation -- MUST
        flag."""
        source = "測" * 20
        assert is_suspiciously_short(source, "     ", "Vietnamese") is True

    def test_single_char_source_below_min_fails_safe(self):
        assert is_suspiciously_short("測", "x", "Vietnamese") is False

    def test_single_char_translation_of_moderate_source_flags(self):
        source = "測" * 20
        assert is_suspiciously_short(source, "字", "Vietnamese") is True

    def test_none_translation_treated_as_empty_no_crash(self):
        source = "測" * 4827
        assert is_suspiciously_short(source, None, "Vietnamese") is True

    def test_none_source_no_crash_fails_safe(self):
        assert is_suspiciously_short(None, "x", "Vietnamese") is False

    def test_none_target_no_crash_fails_safe(self):
        assert is_suspiciously_short("測" * 20, "x", None) is False


class TestMixedScriptAndUnicodeComposition:
    """Confirms composition counting does not miscount (miss-classify) on
    Unicode edge cases in a way that would cause a SPURIOUS flag on a
    proportional, legitimate translation."""

    def test_mixed_cjk_latin_digit_punct_emoji_proportional_translation_not_flagged(self):
        """A cell mixing CJK, Latin, digits, punctuation, and an emoji:
        only CJK and latin-alpha chars count toward E (digits/punctuation/
        emoji excluded). A translation proportional to the counted
        composition must NOT flag."""
        source = "產品ABC型號123規格說明總覽表🎉標題內容備註事項一二三四五六"
        norm = normalize_text(source)
        e = expected_length(norm, "Vietnamese", config.TRUNCATION_GUARD_COEFFICIENTS)
        translation = "x" * (int(e * 0.5) + 1)  # comfortably above the k=0.3 line
        assert is_suspiciously_short(source, translation, "Vietnamese") is False

    def test_fullwidth_digits_not_miscounted_as_latin_alpha(self):
        """Full-width digits (U+FF10-FF19) are `str.isdigit()` True but
        NOT `str.isalpha()` -- confirm they are excluded from latin_alpha
        exactly like ASCII digits, so a source of only full-width digits
        fails safe (E == 0) regardless of translation length."""
        source = "０１２３４５６７８９" * 2
        cjk, latin = count_composition(normalize_text(source))
        assert (cjk, latin) == (0, 0)
        assert is_suspiciously_short(source, "x", "Vietnamese") is False

    def test_cjk_punctuation_excluded_does_not_inflate_expected_length(self):
        """CJK sentence punctuation (。！？、；：
        「」) must NOT be counted as CJK content -- only the real
        CJK letters (測試內容, x2 repeats = 8 chars) count, so E reflects
        real content, not punctuation padding."""
        source = "測試內容。！？、；：「」" * 2
        norm = normalize_text(source)
        cjk, _latin = count_composition(norm)
        assert cjk == 8, "only the 4 real CJK chars x2 repeats should count, punctuation excluded"
        e = expected_length(norm, "Vietnamese", config.TRUNCATION_GUARD_COEFFICIENTS)
        translation = "x" * (int(e * 0.5) + 1)  # proportional to the real (unpadded) content
        assert is_suspiciously_short(source, translation, "Vietnamese") is False

    def test_combining_marks_counted_as_latin_alpha_no_crash(self):
        """A precomposed accented char (e.g. 'é') is `str.isalpha()` True
        and counts as latin_alpha; confirm no crash and a proportional
        translation is not flagged."""
        source = "é" * 10 + "x" * 21  # 31 latin-alpha chars total
        cjk, latin = count_composition(normalize_text(source))
        assert (cjk, latin) == (0, 31)
        e = expected_length(normalize_text(source), "Vietnamese", config.TRUNCATION_GUARD_COEFFICIENTS)
        translation = "y" * (int(e * 0.5) + 1)
        assert is_suspiciously_short(source, translation, "Vietnamese") is False

    def test_rtl_arabic_zwj_and_surrogate_emoji_no_crash(self):
        """RTL Arabic script, a Zero-Width Joiner, and a surrogate-pair
        (ZWJ-sequence) emoji must not raise, and must be handled by the
        same composition rules (Arabic letters are non-CJK `isalpha()` ->
        latin_alpha bucket; ZWJ/emoji are neither -> excluded)."""
        source = "مرحبا بالعالم هذا اختبار طويل بما فيه الكفاية" + "‍" + "\U0001F600\U0001F468‍\U0001F469‍\U0001F467‍\U0001F466"
        norm = normalize_text(source)
        assert len(norm) >= config.TRUNCATION_GUARD_MIN_SOURCE_CHARS
        cjk, latin = count_composition(norm)
        assert cjk == 0
        assert latin > 0
        e = expected_length(norm, "Vietnamese", config.TRUNCATION_GUARD_COEFFICIENTS)
        translation = "z" * (int(e * 0.5) + 1)
        assert is_suspiciously_short(source, translation, "Vietnamese") is False

    def test_bom_prefix_does_not_miscount_or_crash(self):
        """A UTF-8 BOM char (U+FEFF) prefixing the source must not be
        counted as CJK/latin-alpha and must not crash normalize_text /
        count_composition. A genuinely short reply after a BOM-prefixed
        source is still a real flag (not a fail-safe case)."""
        source = "﻿" + "測" * 20
        cjk, latin = count_composition(normalize_text(source))
        assert cjk == 20 and latin == 0
        assert is_suspiciously_short(source, "z", "Vietnamese") is True


class TestInjectionLikeStringsAsTranslationContent:
    """The guard is pure (no I/O/DB/eval surface), but an LLM's returned
    'translation' is untrusted, potentially attacker-shaped text. Confirm
    SQL-like and script-like strings are treated as plain text (no crash,
    correct length/composition accounting), for both a short (flagged) and
    an adequately-long (proportional, not flagged) reply."""

    def test_sql_injection_like_short_translation_flags_no_crash(self):
        source = "測" * 4827
        translation = "'; DROP TABLE users; --"
        assert is_suspiciously_short(source, translation, "Vietnamese") is True

    def test_script_tag_like_short_translation_flags_no_crash(self):
        source = "測" * 4827
        translation = "<script>alert(1)</script>"
        assert is_suspiciously_short(source, translation, "Vietnamese") is True

    def test_sql_like_string_as_source_no_crash(self):
        """An SQL-like string used (implausibly) as the SOURCE must not
        crash; punctuation-heavy content mostly excludes from composition,
        so this exercises the same fail-safe/short-source paths without
        raising."""
        source = "SELECT * FROM users WHERE id = 1 OR 1=1; -- comment padding"
        result = is_suspiciously_short(source, "ok", "Vietnamese")
        assert isinstance(result, bool)


class TestSeededPropertyFuzz:
    """Seeded, deterministic property fuzz (no `hypothesis` dependency in
    this repo's conda env — verified absent; plain `random` with a fixed,
    recorded seed instead). Every assertion targets a real safe-outcome
    invariant, not merely "does not crash":

      1. An uncalibrated/garbage target NEVER flags, for ANY random source/
         translation content (fail-safe invariant 1, ADR-0020).
      2. `is_suspiciously_short` never raises and always returns a bool,
         across CJK/Latin/digit/punctuation/whitespace/exotic-codepoint
         content and a rotating set of targets (crash-safety, but combined
         with (1) and (3) it is not the ONLY assertion).
      3. A translation at least `k * max(coefficient) * len(source) + 100`
         characters long can NEVER flag for the calibrated target, for any
         source composition -- a mathematically guaranteed safe outcome
         derived directly from `E <= max(a,b) * len(norm_source)` (since
         `cjk + latin <= len(norm_source)`), so
         `threshold = k*E <= k*max(a,b)*len(norm_source) <= k*max(a,b)*len(source)`.

    Seeds recorded for replay: 20260711 (invariant 1), 20260712 (invariant
    2), 20260713 (invariant 3).
    """

    _POOL = (
        [chr(cp) for cp in range(0x4E00, 0x4E00 + 200)]   # CJK block
        + list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJ")     # latin
        + list("0123456789")                                # digits
        + list("!@#$%^&*()_+-=[]{}|;:,.<>?/")               # punctuation
        + list(" \t\n")                                     # whitespace
        + ["‍", "﻿", "́", "０", "１"]  # exotic codepoints
    )

    @classmethod
    def _random_string(cls, rng: random.Random, length: int) -> str:
        return "".join(rng.choice(cls._POOL) for _ in range(length))

    def test_uncalibrated_target_never_flags_across_random_inputs(self):
        seed = 20260711
        rng = random.Random(seed)
        for _ in range(200):
            length = rng.randint(0, 6000)
            source = self._random_string(rng, length)
            translation = self._random_string(rng, rng.randint(0, 200))
            result = is_suspiciously_short(source, translation, "some-uncalibrated-target-xyz")
            assert result is False, (
                f"uncalibrated target must fail-safe regardless of content; "
                f"seed={seed} source_len={length}"
            )

    def test_never_raises_and_always_returns_bool_across_random_inputs(self):
        seed = 20260712
        rng = random.Random(seed)
        targets = ["Vietnamese", "vietnamese", "", None, "French", "\U0001F389", "﻿"]
        for _ in range(300):
            length = rng.randint(0, 6000)
            source = self._random_string(rng, length)
            translation = self._random_string(rng, rng.randint(0, 300))
            target = rng.choice(targets)
            try:
                result = is_suspiciously_short(source, translation, target)
            except Exception as exc:  # pragma: no cover - failure path
                pytest.fail(
                    f"is_suspiciously_short raised {exc!r}; seed={seed} "
                    f"source_len={length} target={target!r}"
                )
            assert isinstance(result, bool)

    def test_translation_at_least_double_source_length_never_flags(self):
        seed = 20260713
        rng = random.Random(seed)
        coeffs = config.TRUNCATION_GUARD_COEFFICIENTS
        max_coeff = max(max(a, b) for a, b in coeffs.values())
        k = config.TRUNCATION_GUARD_K
        for _ in range(200):
            length = rng.randint(0, 3000)
            source = self._random_string(rng, length)
            safe_len = int(k * max_coeff * len(source)) + 100
            translation = "z" * safe_len
            assert is_suspiciously_short(source, translation, "Vietnamese") is False, (
                f"mathematically-guaranteed-safe translation length flagged; "
                f"seed={seed} source_len={length} translation_len={safe_len}"
            )
