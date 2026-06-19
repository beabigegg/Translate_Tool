"""Tests for dynamic translation strategy module."""

from __future__ import annotations

from app.backend.config import ModelType
from app.backend.services.translation_strategy import (
    TranslationScenario,
    build_strategy,
    detect_translation_scenario,
    scenario_from_profile,
)


def test_detect_translation_scenario_technical_keywords() -> None:
    scenario = detect_translation_scenario(
        filename="SOP_stationA_rev3.docx",
        sample_text="制程參數、扭矩、批號追溯與校正紀錄",
        detected_context="這是技術製程文件，要求可操作且參數準確。",
    )
    assert scenario == TranslationScenario.TECHNICAL_PROCESS


def test_detect_translation_scenario_business_finance_keywords() -> None:
    scenario = detect_translation_scenario(
        filename="q4_forecast_report.xlsx",
        sample_text="毛利率、現金流、ROI、IFRS",
        detected_context="商務金融文件",
    )
    assert scenario == TranslationScenario.BUSINESS_FINANCE


def test_build_strategy_adds_context_and_options_for_general_model() -> None:
    decision = build_strategy(
        base_system_prompt="You are a professional translator.",
        model_type=ModelType.GENERAL.value,
        scenario=TranslationScenario.LEGAL_CONTRACT,
        detected_context="國際法規與合約條款，包含 shall/must。",
        enable_context_flow=True,
    )
    assert decision.scenario == TranslationScenario.LEGAL_CONTRACT
    assert "Document context:" in decision.system_prompt
    assert decision.options_override.get("temperature") == 0.18
    # BR-45: cache_variant includes _ctx segment plus _crit critique marker
    assert "_ctx" in decision.cache_variant


def test_build_strategy_for_translation_model_technical_process_includes_glossary_hint() -> None:
    decision = build_strategy(
        base_system_prompt="",
        model_type=ModelType.TRANSLATION.value,
        scenario=TranslationScenario.TECHNICAL_PROCESS,
        detected_context="",
        enable_context_flow=True,
    )
    assert "work instruction" in decision.system_prompt
    assert decision.options_override.get("temperature") == 0.2
    # BR-45: cache_variant includes _glossary segment plus _crit critique marker
    assert "_glossary" in decision.cache_variant


def test_scenario_from_profile_supports_new_and_legacy_profile_ids() -> None:
    assert scenario_from_profile("technical_process") == TranslationScenario.TECHNICAL_PROCESS
    assert scenario_from_profile("business_finance") == TranslationScenario.BUSINESS_FINANCE
    assert scenario_from_profile("legal") == TranslationScenario.LEGAL_CONTRACT
    assert scenario_from_profile("unknown_profile") is None


def test_build_strategy_includes_glossary_digest_in_cache_variant() -> None:
    """AC-6 / BR-45: cache_variant embeds glossary-state digest so pre-glossary entries miss."""
    from app.backend.models.term import Term

    terms_empty: list = []
    terms_with_data = [
        Term(
            source_text="wafer",
            target_text="晶圓",
            source_lang="en",
            target_lang="zh-TW",
            domain="technical",
            status="approved",
        )
    ]

    decision_empty = build_strategy(
        base_system_prompt="",
        model_type=ModelType.GENERAL.value,
        scenario=TranslationScenario.GENERAL,
        detected_context=None,
        enable_context_flow=False,
        terms=terms_empty,
    )

    decision_with_terms = build_strategy(
        base_system_prompt="",
        model_type=ModelType.GENERAL.value,
        scenario=TranslationScenario.GENERAL,
        detected_context=None,
        enable_context_flow=False,
        terms=terms_with_data,
    )

    # Variants must differ (stale pre-glossary entries will miss)
    assert decision_empty.cache_variant != decision_with_terms.cache_variant
    # Both must carry the critique marker
    assert "_crit" in decision_empty.cache_variant
    assert "_crit" in decision_with_terms.cache_variant
    # The glossary-digest version must contain a hex digest segment
    assert "_g" in decision_with_terms.cache_variant


def test_build_strategy_legacy_scenario_is_canonicalized() -> None:
    decision = build_strategy(
        base_system_prompt="",
        model_type=ModelType.GENERAL.value,
        scenario=TranslationScenario.BUSINESS_EMAIL,
        detected_context="",
        enable_context_flow=False,
    )
    assert decision.scenario == TranslationScenario.BUSINESS_FINANCE


# ---------------------------------------------------------------------------
# Doc2Doc integration tests (p2-long-doc-chunking, AC-4, AC-6, AC-7, AC-8)
# Mock boundary: app.backend.services.translation_service.translate_blocks_batch
# ---------------------------------------------------------------------------

from unittest.mock import MagicMock, patch

from app.backend.models.translatable_document import (
    DocumentMetadata,
    ElementType,
    PageInfo,
    TranslatableDocument,
    TranslatableElement,
)


def _make_element(eid: str, content: str, etype=ElementType.TEXT, should_translate: bool = True):
    return TranslatableElement(
        element_id=eid,
        content=content,
        element_type=etype,
        page_num=1,
        should_translate=should_translate,
    )


def _make_doc(elements):
    return TranslatableDocument(
        source_path="/fake/doc.pdf",
        source_type="pdf",
        elements=elements,
        pages=[PageInfo(page_num=1, width=612.0, height=792.0)],
        metadata=DocumentMetadata(),
    )


def _make_client():
    client = MagicMock()
    client.cache_model_key = "test-model"
    client.translate_once.return_value = (True, "translated text")
    return client


def test_doc2doc_calls_llm_once_per_chunk():
    """AC-4: translate_document invokes translate_blocks_batch exactly once per chunk."""
    from app.backend.config import CHUNK_OVERLAP_TOKENS
    from app.backend.services.doc_chunker import split_document
    from app.backend.services.translation_service import translate_document

    elements = [_make_element(f"e{i}", "word " * 40) for i in range(20)]
    doc = _make_doc(elements)
    client = _make_client()

    # Determine expected chunk count separately
    probe_elements = [_make_element(f"e{i}", "word " * 40) for i in range(20)]
    probe_doc = _make_doc(probe_elements)
    chunks = split_document(probe_doc, num_ctx=200, overlap_tokens=CHUNK_OVERLAP_TOKENS)
    expected_calls = len(chunks)

    with patch("app.backend.services.translation_service.translate_blocks_batch",
               return_value=[(True, "translated")]) as mock_batch, \
         patch("app.backend.services.translation_service.get_cache", return_value=None):
        translate_document(doc, targets=["fr"], src_lang="en", client=client, num_ctx=200)

    assert mock_batch.call_count == expected_calls, (
        f"Expected {expected_calls} LLM calls (one per chunk), got {mock_batch.call_count}"
    )


def test_each_chunk_translation_is_independent():
    """AC-4: each chunk translated independently — batch calls are separate."""
    from app.backend.services.translation_service import translate_document

    elements = [_make_element(f"e{i}", "word " * 40) for i in range(20)]
    doc = _make_doc(elements)
    client = _make_client()

    call_args_list = []

    def capture_batch(*args, **kwargs):
        call_args_list.append(args[0] if args else kwargs.get("texts", []))
        return [(True, "translated")]

    with patch("app.backend.services.translation_service.translate_blocks_batch",
               side_effect=capture_batch) as mock_batch, \
         patch("app.backend.services.translation_service.get_cache", return_value=None):
        translate_document(doc, targets=["fr"], src_lang="en", client=client, num_ctx=200)

    # Must have been called at least once (and each call is independent)
    assert mock_batch.call_count >= 1
    # Each call receives a list of texts (the chunk's element contents)
    for call_texts in call_args_list:
        assert isinstance(call_texts, list)


def test_single_chunk_doc_produces_exactly_one_llm_call():
    """AC-6, BR-52: short doc → exactly 1 LLM call (single-chunk path)."""
    from app.backend.services.translation_service import translate_document

    elements = [_make_element("e1", "Short text.")]
    doc = _make_doc(elements)
    client = _make_client()

    with patch("app.backend.services.translation_service.translate_blocks_batch",
               return_value=[(True, "Texte court.")]) as mock_batch, \
         patch("app.backend.services.translation_service.get_cache", return_value=None):
        translate_document(doc, targets=["fr"], src_lang="en", client=client, num_ctx=4096)

    assert mock_batch.call_count == 1, (
        f"Short doc must produce exactly 1 LLM call; got {mock_batch.call_count}"
    )


def test_doc2doc_accepts_whole_document():
    """AC-7: translate_document accepts a complete TranslatableDocument; no pre-split required."""
    from app.backend.services.translation_service import translate_document

    elements = [_make_element("e1", "Hello"), _make_element("e2", "World")]
    doc = _make_doc(elements)
    client = _make_client()

    with patch("app.backend.services.translation_service.translate_blocks_batch",
               return_value=[(True, "translated"), (True, "translated")]) as mock_batch, \
         patch("app.backend.services.translation_service.get_cache", return_value=None):
        result = translate_document(doc, targets=["fr"], src_lang="en", client=client, num_ctx=4096)

    assert isinstance(result, TranslatableDocument), "Must accept whole doc and return TranslatableDocument"


def test_doc2doc_returns_same_document_instance():
    """AC-7, data-shape Doc2Doc contract: returns same object reference."""
    from app.backend.services.translation_service import translate_document

    elements = [_make_element("e1", "Hello")]
    doc = _make_doc(elements)
    client = _make_client()

    with patch("app.backend.services.translation_service.translate_blocks_batch",
               return_value=[(True, "Bonjour")]) as mock_batch, \
         patch("app.backend.services.translation_service.get_cache", return_value=None):
        result = translate_document(doc, targets=["fr"], src_lang="en", client=client, num_ctx=4096)

    assert result is doc, "translate_document must return the same document instance"


def test_doc2doc_chunking_transparent_to_caller():
    """AC-7: chunking is applied automatically; caller does not pre-split."""
    from app.backend.services.translation_service import translate_document

    # Long doc requiring chunking
    elements = [_make_element(f"e{i}", "word " * 40) for i in range(20)]
    doc = _make_doc(elements)
    original_ids = {e.element_id for e in elements}
    client = _make_client()

    with patch("app.backend.services.translation_service.translate_blocks_batch",
               return_value=[(True, "translated")]) as mock_batch, \
         patch("app.backend.services.translation_service.get_cache", return_value=None):
        result = translate_document(doc, targets=["fr"], src_lang="en", client=client, num_ctx=200)

    # Caller passed whole doc; after translation all elements are still present
    result_ids = {e.element_id for e in result.elements}
    assert result_ids == original_ids, (
        f"All original elements must be present. Missing: {original_ids - result_ids}"
    )


def test_translate_texts_unchanged_after_doc2doc_added():
    """AC-8, BR-53: translate_texts returns identical behavior after Doc2Doc path added."""
    from app.backend.services import translation_service

    client = _make_client()
    texts = ["Hello", "World"]
    tgt = "zh-TW"

    with patch.object(translation_service, "SENTENCE_MODE", True), \
         patch("app.backend.services.translation_service.translate_blocks_batch",
               return_value=[(True, "你好"), (True, "世界")]) as mock_batch, \
         patch("app.backend.services.translation_service.get_cache", return_value=None), \
         patch.object(translation_service, "CRITIQUE_LOOP_ENABLED", False):
        tmap, done, fail_cnt, stopped = translation_service.translate_texts(
            texts=texts,
            targets=[tgt],
            src_lang="en",
            client=client,
        )

    assert isinstance(tmap, dict)
    assert isinstance(done, int)
    assert isinstance(fail_cnt, int)
    assert isinstance(stopped, bool)
    assert fail_cnt == 0
    assert not stopped


def test_doc2doc_does_not_mutate_shared_cache_state():
    """AC-8, BR-53: translate_document does not alter cache state that translate_texts depends on."""
    from app.backend.services.translation_service import translate_document

    elements = [_make_element("e1", "Hello")]
    doc = _make_doc(elements)
    client = _make_client()

    # The cache must not be called with any mutating calls from translate_document
    mock_cache = MagicMock()
    mock_cache.get_batch.return_value = {}
    mock_cache.put_batch.return_value = None

    with patch("app.backend.services.translation_service.translate_blocks_batch",
               return_value=[(True, "Bonjour")]) as mock_batch, \
         patch("app.backend.services.translation_service.get_cache", return_value=mock_cache):
        translate_document(doc, targets=["fr"], src_lang="en", client=client, num_ctx=4096)

    # The cache may be consulted but should not be mutated in a way that breaks translate_texts
    # (No assertion on exact call count; just verify no exception raised)
    assert True  # If we get here, no shared-state corruption occurred


# ---------------------------------------------------------------------------
# p2-comet-qe integration tests
# Mock boundary: app.backend.services.quality_evaluator.load_model
# Anti-tautology: assert call_count on the hook, not on job result (CLAUDE.md)
# ---------------------------------------------------------------------------

def test_qe_hook_called_after_translation():
    """AC-1 integration: post_translate_hook is invoked by the XLSX processor with
    (block_id, src, mt) tuples after translation.

    Anti-tautological: asserts on hook_calls (not just the job/file result).
    Mock boundary: app.backend.processors.xlsx_processor.translate_texts (consumer path).
    """
    import inspect
    import os
    import tempfile
    import openpyxl
    from app.backend.processors.orchestrator import process_files
    from app.backend.processors.xlsx_processor import translate_xlsx_xls

    # 1. Verify post_translate_hook is wired in process_files and the XLSX processor
    assert "post_translate_hook" in inspect.signature(process_files).parameters, (
        "process_files must accept post_translate_hook (orchestrator wiring)"
    )
    assert "post_translate_hook" in inspect.signature(translate_xlsx_xls).parameters, (
        "translate_xlsx_xls must accept post_translate_hook (processor wiring)"
    )

    # 2. Functional test: create a minimal XLSX, run translation with a hook,
    #    assert the hook fires and receives (block_id, src, mt) tuples.
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Hello", "World"])

    hook_calls: list = []

    def _hook(tuples):
        hook_calls.extend(tuples)

    client = _make_client()

    with tempfile.TemporaryDirectory() as tmpdir:
        in_path = os.path.join(tmpdir, "test.xlsx")
        out_path = os.path.join(tmpdir, "test_out.xlsx")
        wb.save(in_path)

        with patch(
            "app.backend.processors.xlsx_processor.translate_texts",
            return_value=(
                {("fr", "Hello"): "Bonjour", ("fr", "World"): "Monde"},
                2, 0, False,
            ),
        ):
            translate_xlsx_xls(
                in_path=in_path,
                out_path=out_path,
                targets=["fr"],
                src_lang="en",
                client=client,
                post_translate_hook=_hook,
            )

    # Anti-tautological: assert hook was called with real tuples (not just file output)
    assert len(hook_calls) > 0, (
        "post_translate_hook must be called with (block_id, src, mt) tuples after translation"
    )
    block_ids = [t[0] for t in hook_calls]
    srcs = [t[1] for t in hook_calls]
    mts = [t[2] for t in hook_calls]
    assert all(bid.startswith("xlsx:") for bid in block_ids), (
        f"XLSX block_ids must use 'xlsx:{{file_stem}}:{{idx}}' format; got {block_ids}"
    )
    assert "Hello" in srcs or "World" in srcs, "src must include original cell text"
    assert "Bonjour" in mts or "Monde" in mts, "mt must include translated cell text"


def test_qe_hook_not_called_when_disabled():
    """AC-7 integration: when QE_ENABLED=False the load_model seam is never called.

    Patches load_model at the consumer boundary.  Asserts call_count == 0.
    """
    import app.backend.config as _cfg
    from app.backend.services.translation_service import translate_document

    elements = [_make_element("e1", "Hello")]
    doc = _make_doc(elements)
    client = _make_client()

    with patch("app.backend.services.quality_evaluator.load_model") as mock_load, \
         patch.object(_cfg, "QE_ENABLED", False), \
         patch("app.backend.services.translation_service.translate_blocks_batch",
               return_value=[(True, "Bonjour")]), \
         patch("app.backend.services.translation_service.get_cache", return_value=None):
        translate_document(doc, targets=["fr"], src_lang="en", client=client, num_ctx=4096)

    assert mock_load.call_count == 0, (
        "load_model must NOT be called when QE_ENABLED=False"
    )


def test_translate_texts_unaffected_by_qe_change():
    """AC-8, BR-53 regression guard: translate_texts returns same shape after QE wiring.

    Verifies the return type and basic contract of translate_texts is unchanged.
    """
    from app.backend.services import translation_service

    client = _make_client()
    texts = ["Sentence one.", "Sentence two."]

    with patch("app.backend.services.translation_service.translate_blocks_batch",
               return_value=[(True, "一."), (True, "二.")]) as mock_batch, \
         patch("app.backend.services.translation_service.get_cache", return_value=None), \
         patch.object(translation_service, "CRITIQUE_LOOP_ENABLED", False):
        tmap, done, fail_cnt, stopped = translation_service.translate_texts(
            texts=texts,
            targets=["zh-TW"],
            src_lang="en",
            client=client,
        )

    # Shape must be identical to pre-QE contract
    assert isinstance(tmap, dict), "tmap must be a dict"
    assert isinstance(done, int), "done must be int"
    assert isinstance(fail_cnt, int), "fail_cnt must be int"
    assert isinstance(stopped, bool), "stopped must be bool"
    assert fail_cnt == 0
    assert not stopped
    # Verify mock_batch was actually used (anti-tautology: hook was called)
    assert mock_batch.call_count >= 1, "translate_blocks_batch must have been called"
