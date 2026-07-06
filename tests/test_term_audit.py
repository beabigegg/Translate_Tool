"""Tests for TermAudit module (p2-term-audit).

TDD order: these tests are written BEFORE implementation and will fail
until IP-2 (get_rejected), IP-3 (term_audit.py), IP-4 (TerminologyAuditResult),
and IP-5 (job_manager wiring) are complete.

Tautology guards:
  - Integration test patches app.backend.services.job_manager.audit_terms
    (consumer-module binding), NOT app.backend.services.term_audit.audit_terms.
  - Selection tests assert WHICH terms matched, not only len() > 0.
  - test_whole_token_rejected_injection pins substring-of-approved risk.
"""

from __future__ import annotations

import dataclasses
from typing import List, Tuple
from unittest.mock import MagicMock, patch

import pytest

from app.backend.models.term import Term
from app.backend.services.term_db import TermDB


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db(tmp_path):
    """Fresh in-memory TermDB using a temp file."""
    return TermDB(db_path=tmp_path / "test.sqlite")


def _make_term(**kwargs) -> Term:
    """Build a Term with sensible defaults, matching test_term_db.py pattern."""
    defaults = dict(
        source_text="Pin",
        target_text="chân",
        source_lang="zh",
        target_lang="vi",
        domain="technical",
        context_snippet="",
        confidence=1.0,
        usage_count=0,
        status="approved",
    )
    defaults.update(kwargs)
    return Term(**defaults)


def _insert_approved(db: TermDB, **kwargs) -> Term:
    """Insert a term and mark it approved; return the Term."""
    t = _make_term(**kwargs)
    db.insert(t)
    db.approve(t.source_text, t.target_lang, t.domain)
    return t


def _insert_rejected(db: TermDB, **kwargs) -> Term:
    """Insert a term and mark it rejected; return the Term."""
    defaults = dict(status="unverified")
    defaults.update(kwargs)
    t = _make_term(**defaults)
    db.insert(t)
    db.reject(t.source_text, t.target_lang, t.domain)
    return t


# ---------------------------------------------------------------------------
# IP-2 / test_get_rejected_interface
# ---------------------------------------------------------------------------


def test_get_rejected_interface(db):
    """get_rejected(target_lang, domain) returns only rejected terms."""
    from app.backend.services.term_db import TermDB  # noqa: F401

    _insert_approved(db, source_text="Pin", target_text="chân")
    _insert_rejected(db, source_text="BadWord", target_text="từ xấu")
    # A third term that is unverified — should not appear
    db.insert(_make_term(source_text="Ambig", target_text="không rõ", status="unverified"))

    rejected = db.get_rejected("vi", "technical")
    source_texts = [t.source_text for t in rejected]

    assert "BadWord" in source_texts, "get_rejected must return rejected terms"
    assert "Pin" not in source_texts, "get_rejected must NOT return approved terms"
    assert "Ambig" not in source_texts, "get_rejected must NOT return unverified terms"
    # All returned items must have status='rejected'
    for t in rejected:
        assert t.status == "rejected", f"Expected status=rejected, got {t.status}"


def test_get_rejected_filters_by_lang(db):
    """get_rejected scopes to target_lang like get_approved."""
    _insert_rejected(db, source_text="BadVI", target_text="từ xấu vi", target_lang="vi")
    _insert_rejected(db, source_text="BadEN", target_text="bad en", target_lang="en")

    vi_rejected = db.get_rejected("vi", "technical")
    source_texts = [t.source_text for t in vi_rejected]
    assert "BadVI" in source_texts
    assert "BadEN" not in source_texts


# ---------------------------------------------------------------------------
# Unit tests — matching algorithm
# ---------------------------------------------------------------------------


def test_hit_rate_exact_match(db):
    """AC-4: assert WHICH terms matched by target_text value (selection, not count-only)."""
    from app.backend.services.term_audit import audit_terms

    _insert_approved(db, source_text="Pin", target_text="chân")
    _insert_approved(db, source_text="Resistor", target_text="điện trở")
    _insert_approved(db, source_text="Capacitor", target_text="tụ điện")

    # mt contains "chân" and "điện trở" but NOT "tụ điện"
    blocks: List[Tuple[str, str, str]] = [
        ("b1", "Pin is used here", "chân được sử dụng ở đây"),
        ("b2", "Check resistor value", "Kiểm tra giá trị điện trở"),
    ]
    result = audit_terms(blocks, targets=["vi"], domain="technical", term_db=db)

    assert "chân" in result.unapplied_terms or "Pin" in result.unapplied_terms or \
           result.matched_approved >= 2, "chân and điện trở must be counted as hits"
    # The unmatched term must contain the source for "tụ điện"
    assert "Capacitor" in result.unapplied_terms or "tụ điện" in result.unapplied_terms, \
        "Capacitor/tụ điện was absent from mt, must appear in unapplied_terms"
    assert result.terminology_hit_rate == pytest.approx(2 / 3)


def test_hit_rate_case_insensitive(db):
    """AC-4: 'Neural Network' matches 'neural network' in mt."""
    from app.backend.services.term_audit import audit_terms

    _insert_approved(db, source_text="Neural Network", target_text="mạng nơ-ron",
                     source_lang="en", target_lang="vi", domain="ai")

    blocks: List[Tuple[str, str, str]] = [
        ("b1", "Neural Network overview", "Tổng quan về MẠNG NƠ-RON"),
    ]
    result = audit_terms(blocks, targets=["vi"], domain="ai", term_db=db)

    assert result.terminology_hit_rate == pytest.approx(1.0), \
        "Case-insensitive match: MẠNG NƠ-RON must match mạng nơ-ron"
    assert result.matched_approved == 1


def test_unapplied_terms_list(db):
    """AC-8: unapplied_terms list identifies correct terms by source_text value."""
    from app.backend.services.term_audit import audit_terms

    _insert_approved(db, source_text="Pin", target_text="chân")
    _insert_approved(db, source_text="Capacitor", target_text="tụ điện")

    # mt contains "chân" but NOT "tụ điện"
    blocks: List[Tuple[str, str, str]] = [
        ("b1", "Pin here", "chân ở đây"),
    ]
    result = audit_terms(blocks, targets=["vi"], domain="technical", term_db=db)

    assert "Capacitor" in result.unapplied_terms, \
        "Capacitor source_text must appear in unapplied_terms when tụ điện absent from mt"
    assert "Pin" not in result.unapplied_terms, \
        "Pin must NOT appear in unapplied_terms when chân is present in mt"


def test_rejected_injection_detected(db):
    """AC-3: rejected term found in mt → appears in rejected_injections by exact target_text."""
    from app.backend.services.term_audit import audit_terms

    _insert_rejected(db, source_text="BadWord", target_text="từ cấm")

    blocks: List[Tuple[str, str, str]] = [
        ("b1", "src text", "Văn bản có từ cấm ở đây"),
    ]
    result = audit_terms(blocks, targets=["vi"], domain="technical", term_db=db)

    assert "từ cấm" in result.rejected_injections, \
        "Rejected term target_text must appear in rejected_injections when present in mt"


def test_rejected_injection_not_detected(db):
    """AC-3: rejected term absent from mt → rejected_injections == []."""
    from app.backend.services.term_audit import audit_terms

    _insert_rejected(db, source_text="BadWord", target_text="từ cấm")

    blocks: List[Tuple[str, str, str]] = [
        ("b1", "src text", "Văn bản hoàn toàn sạch"),
    ]
    result = audit_terms(blocks, targets=["vi"], domain="technical", term_db=db)

    assert result.rejected_injections == [], \
        "rejected_injections must be empty when no rejected term appears in mt"


def test_vacuous_hit_rate(db):
    """AC-7: total_approved == 0 → terminology_hit_rate == 1.0, no ZeroDivisionError."""
    from app.backend.services.term_audit import audit_terms

    # No approved terms inserted
    blocks: List[Tuple[str, str, str]] = [
        ("b1", "some source", "some translation"),
    ]
    result = audit_terms(blocks, targets=["vi"], domain="technical", term_db=db)

    assert result.terminology_hit_rate == pytest.approx(1.0), \
        "Vacuous hit rate must be 1.0 when no approved terms exist"
    assert result.total_approved == 0
    assert result.matched_approved == 0
    assert result.unapplied_terms == []
    assert result.rejected_injections == []


def test_scope_excludes_non_approved(db):
    """AC-7: unverified/needs_review/rejected terms excluded from denominator."""
    from app.backend.services.term_audit import audit_terms

    # Insert terms with various statuses
    db.insert(_make_term(source_text="Unverified", target_text="chưa xác minh", status="unverified"))
    db.insert(_make_term(source_text="NeedsReview", target_text="cần xem xét", status="needs_review"))
    _insert_rejected(db, source_text="Rejected", target_text="bị từ chối")
    _insert_approved(db, source_text="Approved", target_text="đã phê duyệt")

    # mt contains nothing meaningful
    blocks: List[Tuple[str, str, str]] = [
        ("b1", "source", "translation text"),
    ]
    result = audit_terms(blocks, targets=["vi"], domain="technical", term_db=db)

    # Only approved term should count in denominator
    assert result.total_approved == 1, \
        f"Only approved terms count in denominator; got total_approved={result.total_approved}"


def test_whole_token_rejected_injection(db):
    """Open risk pin: rejected 'bar' is substring of approved 'foobar'; mt='foobar'.

    'bar' must NOT appear in rejected_injections because it is only present as a
    substring of 'foobar', not at a whole-token boundary.
    This test must fail before a boundary-aware matcher is implemented.
    """
    from app.backend.services.term_audit import audit_terms

    _insert_approved(db, source_text="FooBar", target_text="foobar",
                     source_lang="en", target_lang="vi", domain="technical")
    _insert_rejected(db, source_text="Bar", target_text="bar",
                     source_lang="en", target_lang="vi", domain="technical")

    blocks: List[Tuple[str, str, str]] = [
        ("b1", "FooBar reference", "foobar"),
    ]
    result = audit_terms(blocks, targets=["vi"], domain="technical", term_db=db)

    assert "bar" not in result.rejected_injections, (
        "Rejected term 'bar' is only a substring of approved 'foobar'; "
        "whole-token boundary check must NOT flag it as an injection"
    )


def test_hit_rate_20_approved_terms(db):
    """AC-2: 20 approved terms all present in mt → terminology_hit_rate >= 0.95."""
    from app.backend.services.term_audit import audit_terms

    terms_data = [
        ("Term1", "thuật ngữ một"),
        ("Term2", "thuật ngữ hai"),
        ("Term3", "thuật ngữ ba"),
        ("Term4", "thuật ngữ bốn"),
        ("Term5", "thuật ngữ năm"),
        ("Term6", "thuật ngữ sáu"),
        ("Term7", "thuật ngữ bảy"),
        ("Term8", "thuật ngữ tám"),
        ("Term9", "thuật ngữ chín"),
        ("Term10", "thuật ngữ mười"),
        ("Term11", "thuật ngữ mười một"),
        ("Term12", "thuật ngữ mười hai"),
        ("Term13", "thuật ngữ mười ba"),
        ("Term14", "thuật ngữ mười bốn"),
        ("Term15", "thuật ngữ mười lăm"),
        ("Term16", "thuật ngữ mười sáu"),
        ("Term17", "thuật ngữ mười bảy"),
        ("Term18", "thuật ngữ mười tám"),
        ("Term19", "thuật ngữ mười chín"),
        ("Term20", "thuật ngữ hai mươi"),
    ]
    for src, tgt in terms_data:
        _insert_approved(db, source_text=src, target_text=tgt, source_lang="en",
                         target_lang="vi", domain="tech20")

    # Build mt that contains ALL 20 target_text values
    all_target_texts = " ".join(tgt for _, tgt in terms_data)
    blocks: List[Tuple[str, str, str]] = [
        ("b1", "source text", all_target_texts),
    ]
    result = audit_terms(blocks, targets=["vi"], domain="tech20", term_db=db)

    assert result.terminology_hit_rate >= 0.95, \
        f"Expected hit rate >= 0.95 on 20-term fixture; got {result.terminology_hit_rate}"
    assert result.total_approved == 20


# ---------------------------------------------------------------------------
# Data-boundary tests
# ---------------------------------------------------------------------------


def test_empty_block_list(db):
    """Data boundary: blocks=[] → vacuous hit rate, unapplied_terms lists all approved."""
    from app.backend.services.term_audit import audit_terms

    _insert_approved(db, source_text="Pin", target_text="chân")
    _insert_approved(db, source_text="SMD", target_text="SMD")

    result = audit_terms([], targets=["vi"], domain="technical", term_db=db)

    # With 2 approved terms and no blocks: matched_approved=0, total_approved=2 → hit_rate=0.0
    assert result.total_approved == 2
    assert result.matched_approved == 0
    assert result.terminology_hit_rate == pytest.approx(0.0), \
        "Empty blocks with 2 approved terms → 0 matched → hit rate is 0.0"
    # All approved terms unapplied — unapplied_terms stores source_text
    assert "Pin" in result.unapplied_terms, "Pin source_text must be in unapplied_terms when blocks=[]"
    assert "SMD" in result.unapplied_terms, "SMD source_text must be in unapplied_terms when blocks=[]"
    assert result.rejected_injections == []


def test_zero_approved_terms(db):
    """Data boundary: no approved terms → terminology_hit_rate=1.0, empty lists."""
    from app.backend.services.term_audit import audit_terms

    blocks: List[Tuple[str, str, str]] = [
        ("b1", "some source", "some translation"),
    ]
    result = audit_terms(blocks, targets=["vi"], domain="technical", term_db=db)

    assert result.terminology_hit_rate == pytest.approx(1.0)
    assert result.unapplied_terms == []
    assert result.rejected_injections == []
    assert result.total_approved == 0
    assert result.matched_approved == 0


def test_multi_language_target(db):
    """Data boundary: audit scoped per (target_lang, domain); different-lang terms excluded."""
    from app.backend.services.term_audit import audit_terms

    # Approved term for French
    _insert_approved(db, source_text="Pin", target_text="broche", target_lang="fr",
                     source_lang="en", domain="technical")
    # Approved term for Vietnamese
    _insert_approved(db, source_text="Pin", target_text="chân", target_lang="vi",
                     source_lang="en", domain="technical")

    # Audit only for "vi" — should see only the vi approved term
    blocks: List[Tuple[str, str, str]] = [
        ("b1", "Pin here", "chân ở đây"),
    ]
    result = audit_terms(blocks, targets=["vi"], domain="technical", term_db=db)

    assert result.total_approved == 1, \
        "Multi-lang: only vi-scoped terms should count in denominator"
    assert result.terminology_hit_rate == pytest.approx(1.0), \
        "vi term 'chân' is present in mt; hit_rate should be 1.0"


# ---------------------------------------------------------------------------
# Contract tests
# ---------------------------------------------------------------------------


def test_result_shape_conforms_to_data_contract():
    """AC-5: TerminologyAuditResult has exactly 5 fields as per data-shape-contract.md."""
    from app.backend.services.term_audit import TerminologyAuditResult

    expected_fields = {
        "terminology_hit_rate",
        "unapplied_terms",
        "rejected_injections",
        "total_approved",
        "matched_approved",
    }
    actual_fields = {f.name for f in dataclasses.fields(TerminologyAuditResult)}

    assert actual_fields == expected_fields, (
        f"TerminologyAuditResult must have exactly 5 fields per contract. "
        f"Expected: {expected_fields}, Got: {actual_fields}"
    )


def test_no_parallel_report_format(tmp_path):
    """AC-5: audit result attaches to JobRecord.audit, not a new parallel structure."""
    from app.backend.services.job_manager import JobRecord

    job = JobRecord(
        job_id="test-job",
        input_dir=tmp_path / "input",
        output_dir=tmp_path / "output",
    )

    assert hasattr(job, "audit"), "JobRecord must have an 'audit' field"
    assert job.audit is None, "JobRecord.audit must default to None"


# ---------------------------------------------------------------------------
# Integration test (anti-tautology: wrong-entry-point guard)
# ---------------------------------------------------------------------------


def test_audit_wired_at_hook_seam(tmp_path):
    """AC-1: audit_terms is called via _run_job (not translate_document).

    Patches app.backend.services.job_manager.audit_terms at the consumer-module
    binding (CLAUDE.md mock-binding lesson). Calls _run_job via create_job() and
    waits for the thread. Asserts mock.call_count >= 1.

    Does NOT call translate_document() — that wrapper doesn't reach the
    post_translate_hook seam (CLAUDE.md wrong-entry-point lesson).
    """
    from unittest.mock import MagicMock, patch
    import threading
    from app.backend.services.term_audit import TerminologyAuditResult

    dummy_result = TerminologyAuditResult(
        terminology_hit_rate=1.0,
        unapplied_terms=[],
        rejected_injections=[],
        total_approved=0,
        matched_approved=0,
    )

    with patch("app.backend.services.job_manager.audit_terms",
               return_value=dummy_result) as mock_audit, \
         patch("app.backend.services.job_manager.process_files",
               return_value=(1, 1, False, None, {"extracted": 0, "skipped": 0, "added": 0}, None)) as mock_pf, \
         patch("app.backend.services.job_manager.QE_ENABLED", False), \
         patch("app.backend.services.job_manager.TermDB") as mock_termdb_cls:

        mock_termdb_cls.return_value = MagicMock()

        from app.backend.services.job_manager import JobManager
        from app.backend.services.model_router import RouteGroup

        jm = JobManager()

        # Create minimal fake uploaded files
        in_dir = tmp_path / "upload"
        in_dir.mkdir()
        fake_file = in_dir / "test.txt"
        fake_file.write_text("hello")

        route_group = RouteGroup(
            model="test-model",
            targets=["vi"],
            profile_id="general",
            model_type="general",
            provider=None,
        )

        job = jm.create_job(
            uploaded_files=[fake_file],
            route_groups=[route_group],
            src_lang="en",
            include_headers=False,
        )

        # Wait for the job thread to finish
        if job.thread:
            job.thread.join(timeout=10.0)

        assert mock_audit.call_count >= 1, (
            f"audit_terms must be called at least once via _run_job; "
            f"call_count={mock_audit.call_count}"
        )


# ---------------------------------------------------------------------------
# Resilience test
# ---------------------------------------------------------------------------


def test_audit_disabled_when_exception(tmp_path):
    """BR-61: audit_terms raises RuntimeError → job_record.audit=None, job not failed."""
    from unittest.mock import MagicMock, patch

    with patch("app.backend.services.job_manager.audit_terms",
               side_effect=RuntimeError("audit exploded")) as mock_audit, \
         patch("app.backend.services.job_manager.process_files",
               return_value=(1, 1, False, None, {"extracted": 0, "skipped": 0, "added": 0}, None)), \
         patch("app.backend.services.job_manager.QE_ENABLED", False), \
         patch("app.backend.services.job_manager.TermDB") as mock_termdb_cls:

        mock_termdb_cls.return_value = MagicMock()

        from app.backend.services.job_manager import JobManager
        from app.backend.services.model_router import RouteGroup

        jm = JobManager()

        in_dir = tmp_path / "upload2"
        in_dir.mkdir()
        fake_file = in_dir / "test.txt"
        fake_file.write_text("hello")

        route_group = RouteGroup(
            model="test-model",
            targets=["vi"],
            profile_id="general",
            model_type="general",
            provider=None,
        )

        job = jm.create_job(
            uploaded_files=[fake_file],
            route_groups=[route_group],
            src_lang="en",
            include_headers=False,
        )

        if job.thread:
            job.thread.join(timeout=10.0)

        assert mock_audit.call_count >= 1, "audit_terms must have been called"
        assert job.audit is None, \
            "job_record.audit must be None when audit_terms raises an exception (BR-61)"
        assert job.status != "failed", \
            "Job must NOT fail when audit_terms raises — safe degradation (BR-61)"


def test_audit_skipped_when_term_extraction_disabled(tmp_path):
    """term_db is None when enable_term_extraction=False — audit_terms must not
    be called at all (rather than being called and raising AttributeError on
    term_db.get_approved), and job_record.audit stays None without a crash."""
    from unittest.mock import MagicMock, patch

    with patch("app.backend.services.job_manager.audit_terms") as mock_audit, \
         patch("app.backend.services.job_manager.process_files",
               return_value=(1, 1, False, None, {"extracted": 0, "skipped": 0, "added": 0}, None)), \
         patch("app.backend.services.job_manager.QE_ENABLED", False):

        from app.backend.services.job_manager import JobManager
        from app.backend.services.model_router import RouteGroup

        jm = JobManager()

        in_dir = tmp_path / "upload3"
        in_dir.mkdir()
        fake_file = in_dir / "test.txt"
        fake_file.write_text("hello")

        route_group = RouteGroup(
            model="test-model",
            targets=["vi"],
            profile_id="general",
            model_type="general",
            provider=None,
        )

        job = jm.create_job(
            uploaded_files=[fake_file],
            route_groups=[route_group],
            src_lang="en",
            include_headers=False,
            enable_term_extraction=False,
        )

        if job.thread:
            job.thread.join(timeout=10.0)

        assert mock_audit.call_count == 0, (
            "audit_terms must not be called when term_db is None "
            "(enable_term_extraction=False)"
        )
        assert job.audit is None
        assert job.status != "failed"
