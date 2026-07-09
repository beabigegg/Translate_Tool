"""Tests for cloud-path document-context summary parity (BR-109).

Change: cloud-doc-context-summary

Covers AC-1..AC-7 (change-classification.md):
  AC-1: cloud active client generates the summary, no local Ollama required.
  AC-2: summary injected as "Document context: <summary>" into the system prompt
        via the existing downstream wiring.
  AC-3: both CONTEXT_DETECTION_ENABLED and QWEN_CONTEXT_FLOW_ENABLED still gate
        the behavior (AND-gated) on the cloud path.
  AC-4: client._is_translation_dedicated() still skips summary generation.
  AC-5: a failed/empty cloud summary call degrades gracefully (no preamble,
        job never aborts).
  AC-6: local-Ollama context detection is unchanged.
  AC-7: no scope creep into the injection wiring or JSON structured I/O.

Mock boundaries (per test-plan.md Notes):
  - requests.Session.post for integration/AC-1/AC-2/AC-6 (network boundary).
  - app.backend.processors.orchestrator._detect_document_context (same-module
    attribute; call site is unqualified) for AC-3/AC-4 guard tests, asserted
    by call-count.
  - Direct calls to _detect_document_context with a capability-restricted
    MagicMock(spec=["complete"]) for the AC-1/AC-5 unit tests, so an
    accidental fall-back to an Ollama-only private method raises
    AttributeError (caught internally) rather than silently succeeding --
    turning a wrong-seam regression into a loud assertion failure on the
    returned content, not just a call-count check.

Torch-free: no COMET/QE imports anywhere in this file.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.backend.clients.ollama_client import OllamaClient
from app.backend.clients.openai_compatible_client import OpenAICompatibleClient
from app.backend.processors.orchestrator import _detect_document_context, process_files


# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

_PANJIT_CFG = {
    "providers": [
        {
            "id": "panjit",
            "type": "openai",
            "enabled": True,
            "base_url": "http://panjit-mock:8080",
            "api_key": "test-key-panjit",
            "models": {"translate": "gpt-oss:120b"},
        },
        {
            "id": "ollama-local",
            "type": "ollama",
            "enabled": True,
            "base_url": "http://localhost:11434",
            "api_key": "",
            "models": {"translate": "qwen3.5:9b"},
        },
    ],
    "routing": {"default": {"model": "gpt-oss:120b", "provider": "panjit", "profile": "general"}},
    "fallback_chain": ["panjit", "deepseek"],
}


def _make_real_docx(tmp_path: Path, text: str) -> Path:
    """Write a minimal but structurally valid .docx so _sample_file_text
    extracts real, non-empty text (required to satisfy the `sample` guard
    condition at orchestrator.py's context-detection call site)."""
    import docx as _docx

    src = tmp_path / "test.docx"
    doc = _docx.Document()
    doc.add_paragraph(text)
    doc.save(str(src))
    return src


def _mock_post_with_content(content: str):
    """Build a requests.Session.post side_effect returning a fixed chat-completion body."""

    def _mock_post(url, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"choices": [{"message": {"content": content}}]}
        return resp

    return _mock_post


def _make_capturing_translate_docx(captured: dict, stopped: bool = False):
    """Build a translate_docx stub that snapshots client.system_prompt at
    call time.

    orchestrator.process_files' per-file `finally:` clause unconditionally
    resets `client.system_prompt = base_system_prompt` after every file
    (pre-existing cleanup, out of scope for this change) -- so the
    scenario-injected value is only observable at translate_docx call time,
    not by inspecting `client.system_prompt` after process_files() returns.
    """

    def _fn(src_path, out_path, targets, src_lang, client, **kwargs):
        captured["system_prompt"] = client.system_prompt
        return stopped

    return _fn


# ---------------------------------------------------------------------------
# AC-1: cloud active client used for the summary; no local Ollama required
# ---------------------------------------------------------------------------

def test_cloud_active_client_used_for_summary_not_local_ollama():
    """AC-1 (unit): _detect_document_context calls client.complete(), the shared
    seam BOTH clients implement -- not an Ollama-only private method.

    The fake cloud client is capability-restricted to only `complete` via
    MagicMock(spec=["complete"]); if the implementation regressed to an
    Ollama-only method, accessing it would raise AttributeError (caught by
    _detect_document_context's try/except) and silently return "" -- which
    the content assertion below would catch as a hard failure.
    """
    cloud_client = MagicMock(spec=["complete"])
    cloud_client.complete.return_value = (True, "This document is a purchase order.")

    result = _detect_document_context(
        cloud_client, "PO number 12345, widget parts, quantity 500.", log=lambda s: None, target_lang="en"
    )

    cloud_client.complete.assert_called_once()
    prompt_arg = cloud_client.complete.call_args[0][0]
    assert "PO number 12345" in prompt_arg
    assert result == "This document is a purchase order."


def test_cloud_summary_generated_without_local_ollama_present(tmp_path):
    """AC-1 (integration): the document-context summary is produced via the
    active cloud client's HTTP path; the local OllamaClient's raw-completion
    method is never invoked."""
    src_docx = _make_real_docx(tmp_path, "This is a purchase order for widget parts.")
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    post_urls = []

    def _mock_post(url, **kwargs):
        post_urls.append(url)
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"choices": [{"message": {"content": "A purchase order document."}}]}
        return resp

    with patch("app.backend.config.load_providers_config", return_value=_PANJIT_CFG), \
         patch("requests.Session.post", side_effect=_mock_post), \
         patch("app.backend.processors.orchestrator.translate_docx", return_value=False), \
         patch.object(OllamaClient, "_call_ollama") as mock_ollama_call:
        result = process_files(
            files=[src_docx],
            output_dir=out_dir,
            targets=["French"],
            src_lang="English",
            include_headers_shapes_via_com=False,
            ollama_model="qwen3.5:9b",
            model_type="general",
            system_prompt="",
            profile_id="general",
            provider_id="panjit",
        )

    _, _, stopped, _client, _term, winning_provider = result
    assert stopped is False
    assert winning_provider == "panjit"
    mock_ollama_call.assert_not_called()
    assert any("/v1/chat/completions" in u for u in post_urls), (
        "cloud completions endpoint must have been called for the summary"
    )


# ---------------------------------------------------------------------------
# AC-2: summary injected as "Document context: <summary>" into the system prompt
# ---------------------------------------------------------------------------

def test_cloud_summary_injected_as_document_context_in_system_prompt(tmp_path):
    """AC-2 / BR-109 / ADR-0016: the cloud-generated summary reaches the
    OUTGOING request payload as system-channel content on the real
    translate_once() call -- not merely assigned to the `client.system_prompt`
    attribute (which was formerly an orchestrator-compatibility stub whose
    writes were silently discarded on the cloud path). The translatable user
    payload must stay clean (no bleed of the preamble into it).

    DYNAMIC_SCENARIO_STRATEGY_ENABLED is patched off to isolate this
    assertion from scenario-detection heuristics (out of scope; already
    covered by tests/test_translation_strategy.py), exercising the
    non-dynamic else-branch literal at orchestrator.py instead.

    The `translate_docx` stub simulates the one real behavior that matters
    here: dispatching a segment through the resolved client via
    `client.translate_once(...)`, so the scenario-injected
    `client.system_prompt` actually flows through to the outgoing HTTP
    request -- this is the seam a "silently ignored" regression would break,
    unlike inspecting the attribute after the call (asserted as a tautology
    in the prior version of this test).
    """
    src_docx = _make_real_docx(tmp_path, "This document is an engineering change request for a wafer fab line.")
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    summary_text = "An engineering change request for a semiconductor fab line."
    post_bodies: list = []

    def _mock_post(url, **kwargs):
        post_bodies.append(kwargs.get("json", {}))
        resp = MagicMock()
        resp.status_code = 200
        # 1st POST = the context-detection summary call; every subsequent
        # POST = the real translate_once call driven by the stub below.
        content = summary_text if len(post_bodies) == 1 else "Bonjour, demande de modification technique."
        resp.json.return_value = {"choices": [{"message": {"content": content}}]}
        return resp

    def _translate_docx_dispatches_one_segment(src_path, out_path, targets, src_lang, client, **kwargs):
        client.translate_once("Engineering change request text.", targets[0], src_lang)
        return False

    with patch("app.backend.config.load_providers_config", return_value=_PANJIT_CFG), \
         patch("requests.Session.post", side_effect=_mock_post), \
         patch("app.backend.processors.orchestrator.translate_docx", side_effect=_translate_docx_dispatches_one_segment), \
         patch("app.backend.processors.orchestrator.DYNAMIC_SCENARIO_STRATEGY_ENABLED", False):
        result = process_files(
            files=[src_docx],
            output_dir=out_dir,
            targets=["French"],
            src_lang="English",
            include_headers_shapes_via_com=False,
            ollama_model="qwen3.5:9b",
            model_type="general",
            system_prompt="You are a professional translator.",
            profile_id="general",
            provider_id="panjit",
        )

    _, _, stopped, _client, _term, winning_provider = result
    assert stopped is False
    assert winning_provider == "panjit"

    assert len(post_bodies) >= 2, "expected a summary POST plus a translate_once POST"
    translate_body = post_bodies[-1]
    messages = translate_body["messages"]

    system_messages = [m for m in messages if m["role"] == "system"]
    assert len(system_messages) == 1, f"expected exactly one system message, got {system_messages!r}"
    assert f"Document context: {summary_text}" in system_messages[0]["content"]

    user_messages = [m for m in messages if m["role"] == "user"]
    assert not any(f"Document context: {summary_text}" in m["content"] for m in user_messages), (
        "the injected summary must never bleed into the translatable user payload"
    )


# ---------------------------------------------------------------------------
# AC-3: both flags AND-gate the cloud path (negative cases, call-count asserts)
# ---------------------------------------------------------------------------

def test_context_detection_disabled_skips_cloud_summary(tmp_path):
    """AC-3: CONTEXT_DETECTION_ENABLED=False must skip the summary even on the
    cloud path (call-count assertion, not happy-path)."""
    src_docx = _make_real_docx(tmp_path, "Some engineering document text.")
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    with patch("app.backend.config.load_providers_config", return_value=_PANJIT_CFG), \
         patch("requests.Session.post", side_effect=_mock_post_with_content("n/a")), \
         patch("app.backend.processors.orchestrator.translate_docx", return_value=False), \
         patch("app.backend.processors.orchestrator.CONTEXT_DETECTION_ENABLED", False), \
         patch("app.backend.processors.orchestrator._detect_document_context") as mock_detect:
        process_files(
            files=[src_docx],
            output_dir=out_dir,
            targets=["French"],
            src_lang="English",
            include_headers_shapes_via_com=False,
            ollama_model="qwen3.5:9b",
            model_type="general",
            system_prompt="",
            profile_id="general",
            provider_id="panjit",
        )

    mock_detect.assert_not_called()


def test_qwen_context_flow_disabled_skips_cloud_summary(tmp_path):
    """AC-3: QWEN_CONTEXT_FLOW_ENABLED=False must skip the summary even on the
    cloud path (call-count assertion, not happy-path)."""
    src_docx = _make_real_docx(tmp_path, "Some engineering document text.")
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    with patch("app.backend.config.load_providers_config", return_value=_PANJIT_CFG), \
         patch("requests.Session.post", side_effect=_mock_post_with_content("n/a")), \
         patch("app.backend.processors.orchestrator.translate_docx", return_value=False), \
         patch("app.backend.processors.orchestrator.QWEN_CONTEXT_FLOW_ENABLED", False), \
         patch("app.backend.processors.orchestrator._detect_document_context") as mock_detect:
        process_files(
            files=[src_docx],
            output_dir=out_dir,
            targets=["French"],
            src_lang="English",
            include_headers_shapes_via_com=False,
            ollama_model="qwen3.5:9b",
            model_type="general",
            system_prompt="",
            profile_id="general",
            provider_id="panjit",
        )

    mock_detect.assert_not_called()


# ---------------------------------------------------------------------------
# AC-4: translation-dedicated ACTIVE client still skips summary generation
# ---------------------------------------------------------------------------

def test_translation_dedicated_cloud_client_skips_summary(tmp_path):
    """AC-4: when the ACTIVE cloud client reports _is_translation_dedicated()
    == True, the summary is skipped exactly as before (call-count assertion)."""
    src_docx = _make_real_docx(tmp_path, "Some engineering document text.")
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    with patch("app.backend.config.load_providers_config", return_value=_PANJIT_CFG), \
         patch("requests.Session.post", side_effect=_mock_post_with_content("n/a")), \
         patch("app.backend.processors.orchestrator.translate_docx", return_value=False), \
         patch.object(OpenAICompatibleClient, "_is_translation_dedicated", return_value=True), \
         patch("app.backend.processors.orchestrator._detect_document_context") as mock_detect:
        process_files(
            files=[src_docx],
            output_dir=out_dir,
            targets=["French"],
            src_lang="English",
            include_headers_shapes_via_com=False,
            ollama_model="qwen3.5:9b",
            model_type="general",
            system_prompt="",
            profile_id="general",
            provider_id="panjit",
        )

    mock_detect.assert_not_called()


# ---------------------------------------------------------------------------
# AC-5: graceful degradation -- exception or empty result never aborts the job
# ---------------------------------------------------------------------------

def test_detect_document_context_returns_empty_on_cloud_call_exception():
    """AC-5 (unit): client.complete() raising, or returning (False, ""), must
    not propagate out of _detect_document_context -- it degrades to ""."""
    cloud_client_raises = MagicMock(spec=["complete"])
    cloud_client_raises.complete.side_effect = RuntimeError("cloud provider unreachable")
    assert _detect_document_context(cloud_client_raises, "sample text", log=lambda s: None) == ""

    cloud_client_empty = MagicMock(spec=["complete"])
    cloud_client_empty.complete.return_value = (False, "")
    assert _detect_document_context(cloud_client_empty, "sample text", log=lambda s: None) == ""


def test_job_continues_with_no_preamble_when_cloud_summary_empty(tmp_path):
    """AC-5 (resilience): an empty cloud summary response degrades to no
    preamble; the job completes normally (stopped=False), never aborts."""
    src_docx = _make_real_docx(tmp_path, "Some engineering document text.")
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    captured: dict = {}

    with patch("app.backend.config.load_providers_config", return_value=_PANJIT_CFG), \
         patch("requests.Session.post", side_effect=_mock_post_with_content("")), \
         patch("app.backend.processors.orchestrator.translate_docx", side_effect=_make_capturing_translate_docx(captured)), \
         patch("app.backend.processors.orchestrator.DYNAMIC_SCENARIO_STRATEGY_ENABLED", False):
        result = process_files(
            files=[src_docx],
            output_dir=out_dir,
            targets=["French"],
            src_lang="English",
            include_headers_shapes_via_com=False,
            ollama_model="qwen3.5:9b",
            model_type="general",
            system_prompt="Base prompt.",
            profile_id="general",
            provider_id="panjit",
        )

    _, _, stopped, _client, _term, winning_provider = result
    assert stopped is False
    assert winning_provider == "panjit"
    assert "Document context:" not in captured["system_prompt"]


# ---------------------------------------------------------------------------
# AC-6: local-Ollama context detection is unchanged
# ---------------------------------------------------------------------------

def test_local_ollama_context_detection_unchanged(tmp_path):
    """AC-6: the local-Ollama path still generates and injects the summary
    identically to before this change (byte-identical HTTP call via
    complete() -> _call_ollama(_build_no_system_payload(prompt)))."""
    src_docx = _make_real_docx(tmp_path, "Some engineering document text.")
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    summary_text = "An engineering specification document."
    captured: dict = {}

    with patch.object(OllamaClient, "_call_ollama", return_value=(True, summary_text)) as mock_call, \
         patch("app.backend.processors.orchestrator.translate_docx", side_effect=_make_capturing_translate_docx(captured)), \
         patch("app.backend.processors.orchestrator.DYNAMIC_SCENARIO_STRATEGY_ENABLED", False):
        result = process_files(
            files=[src_docx],
            output_dir=out_dir,
            targets=["French"],
            src_lang="English",
            include_headers_shapes_via_com=False,
            ollama_model="qwen3.5:9b",
            model_type="general",
            system_prompt="Base prompt.",
            profile_id="general",
            provider_id=None,
        )

    _, _, stopped, _client, _term, winning_provider = result
    assert stopped is False
    assert winning_provider == "ollama-local"
    assert mock_call.called
    assert captured["system_prompt"] == f"Base prompt.\n\nDocument context: {summary_text}"


# ---------------------------------------------------------------------------
# AC-7: no scope creep -- injection wiring and JSON structured I/O untouched
# ---------------------------------------------------------------------------

def test_no_scope_creep_into_injection_wiring_or_json_io():
    """AC-7: only the generation seam changed. The LLMClient Protocol stays
    at exactly 5 methods (complete() intentionally excluded), the downstream
    "Document context:" injection wiring is untouched, and no JSON
    structured translation I/O (Step 3, a separate tracked change) was
    introduced into _detect_document_context."""
    from app.backend.clients.base_llm_client import LLMClient
    from app.backend.services import translation_strategy
    import app.backend.processors.orchestrator as orch_module

    methods = [
        name for name, member in inspect.getmembers(LLMClient)
        if not name.startswith("_") and callable(getattr(LLMClient, name, None))
    ]
    assert len(methods) == 5, f"Expected 5 Protocol methods, got {len(methods)}: {methods}"
    assert "complete" not in methods, "complete() must stay off the LLMClient Protocol"

    strategy_src = inspect.getsource(translation_strategy.build_strategy)
    assert 'f"Document context: {detected_context' in strategy_src, (
        "build_strategy's Document-context injection literal must be unchanged"
    )

    detect_src = inspect.getsource(orch_module._detect_document_context)
    assert "json.loads" not in detect_src
    assert "{\"translation\"" not in detect_src
