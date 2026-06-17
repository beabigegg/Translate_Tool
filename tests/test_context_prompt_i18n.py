"""Unit tests for context-detection prompt i18n (AC-1..AC-3) and
NUM_CTX env resolution (AC-4..AC-7).

Change: p1-prompt-i18n-numctx
"""

from __future__ import annotations

import importlib
import os
from typing import Callable
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Import the helper from wherever the implementation landed.
# Primary: orchestrator.py (no import cycle discovered).
# Fallback: app.backend.services.context_prompts (leaf module created if a
# cycle was found during backend-engineer phase).
# ---------------------------------------------------------------------------
try:
    from app.backend.processors.orchestrator import _get_context_detection_prompt  # type: ignore[attr-defined]
except ImportError:
    from app.backend.services.context_prompts import _get_context_detection_prompt  # type: ignore[import]


# ---------------------------------------------------------------------------
# AC-1: template selected for en / zh-TW / ja
# ---------------------------------------------------------------------------

def test_template_selected_for_en_zhtw_ja() -> None:
    en_template = _get_context_detection_prompt("en")
    zhtw_template = _get_context_detection_prompt("zh-TW")
    ja_template = _get_context_detection_prompt("ja")

    assert en_template, "en template must be non-empty"
    assert zhtw_template, "zh-TW template must be non-empty"
    assert ja_template, "ja template must be non-empty"

    # zh-TW template must contain Traditional Chinese characters
    # (the existing prompt uses characters such as 請用一句話 / 描述)
    assert any(
        marker in zhtw_template for marker in ("請用一句話", "描述", "文件")
    ), "zh-TW template must contain Traditional Chinese characters"

    # en template must NOT contain CJK characters
    cjk_range = range(0x4E00, 0x9FFF + 1)
    has_cjk = any(ord(ch) in cjk_range for ch in en_template)
    assert not has_cjk, "en template must not contain Chinese characters"

    # all three templates are distinct
    assert en_template != zhtw_template, "en and zh-TW templates must differ"
    assert en_template != ja_template, "en and ja templates must differ"
    assert zhtw_template != ja_template, "zh-TW and ja templates must differ"


# ---------------------------------------------------------------------------
# AC-2: unlisted lang falls back to en
# ---------------------------------------------------------------------------

def test_unlisted_lang_falls_back_to_en() -> None:
    en_template = _get_context_detection_prompt("en")
    assert _get_context_detection_prompt("ko") == en_template, \
        "ko (unlisted) must fall back to en template"
    assert _get_context_detection_prompt("fr") == en_template, \
        "fr (unlisted) must fall back to en template"


# ---------------------------------------------------------------------------
# AC-3: immediate path (_detect_document_context) uses the helper
# ---------------------------------------------------------------------------

def test_immediate_and_deferred_use_same_template() -> None:
    """Assert _detect_document_context passes target_lang to _get_context_detection_prompt
    and that the resulting prompt sent to the LLM contains the sentinel returned by the helper.
    """
    sentinel = "SENTINEL_PROMPT_XYZ"

    # Import here to avoid module-level import errors if orchestrator has heavy deps
    try:
        import app.backend.processors.orchestrator as orch_module
    except ImportError:
        pytest.skip("orchestrator module not importable in this environment")

    mock_client = MagicMock()
    mock_client._build_no_system_payload.return_value = {"prompt": sentinel}
    mock_client._call_ollama.return_value = (True, "detected context")

    helper_path: str
    if hasattr(orch_module, "_get_context_detection_prompt"):
        helper_path = "app.backend.processors.orchestrator._get_context_detection_prompt"
    else:
        helper_path = "app.backend.services.context_prompts._get_context_detection_prompt"

    with patch(helper_path, return_value=sentinel) as mock_helper:
        orch_module._detect_document_context(
            client=mock_client,
            sample="sample text",
            log=lambda s: None,
            target_lang="ja",
        )
        mock_helper.assert_called_once_with("ja")

    # Verify the sentinel was passed to the LLM payload builder
    call_args = mock_client._build_no_system_payload.call_args
    assert call_args is not None, "_build_no_system_payload was not called"
    prompt_arg = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
    assert sentinel in prompt_arg, \
        f"Prompt sent to LLM must contain the helper sentinel; got: {prompt_arg!r}"


# ---------------------------------------------------------------------------
# NUM_CTX tests — helpers
# ---------------------------------------------------------------------------

_NUM_CTX_VARS = ("GENERAL_NUM_CTX", "TRANSLATION_NUM_CTX", "OLLAMA_NUM_CTX")


def _clear_num_ctx_env() -> dict:
    """Remove all three NUM_CTX vars from os.environ; return saved values for restore."""
    saved = {}
    for var in _NUM_CTX_VARS:
        val = os.environ.pop(var, None)
        if val is not None:
            saved[var] = val
    return saved


def _restore_env(saved: dict) -> None:
    for var in _NUM_CTX_VARS:
        os.environ.pop(var, None)
    os.environ.update(saved)


def _reload_config():
    """Reload app.backend.config and return the fresh module."""
    import app.backend.config as cfg
    importlib.reload(cfg)
    return cfg


# ---------------------------------------------------------------------------
# AC-4: GENERAL_NUM_CTX env overrides independently
# ---------------------------------------------------------------------------

def test_general_num_ctx_env_overrides_independently() -> None:
    saved = _clear_num_ctx_env()
    try:
        os.environ["GENERAL_NUM_CTX"] = "2048"
        cfg = _reload_config()
        assert cfg.GENERAL_NUM_CTX == 2048, \
            f"GENERAL_NUM_CTX should be 2048, got {cfg.GENERAL_NUM_CTX}"
        assert cfg.TRANSLATION_NUM_CTX == 3072, \
            f"TRANSLATION_NUM_CTX should be default 3072, got {cfg.TRANSLATION_NUM_CTX}"
    finally:
        _restore_env(saved)
        _reload_config()


# ---------------------------------------------------------------------------
# AC-5: TRANSLATION_NUM_CTX env overrides independently
# ---------------------------------------------------------------------------

def test_translation_num_ctx_env_overrides_independently() -> None:
    saved = _clear_num_ctx_env()
    try:
        os.environ["TRANSLATION_NUM_CTX"] = "1536"
        cfg = _reload_config()
        assert cfg.TRANSLATION_NUM_CTX == 1536, \
            f"TRANSLATION_NUM_CTX should be 1536, got {cfg.TRANSLATION_NUM_CTX}"
        assert cfg.GENERAL_NUM_CTX == 4096, \
            f"GENERAL_NUM_CTX should be default 4096, got {cfg.GENERAL_NUM_CTX}"
    finally:
        _restore_env(saved)
        _reload_config()


# ---------------------------------------------------------------------------
# AC-6: fallback chain — OLLAMA_NUM_CTX then defaults
# ---------------------------------------------------------------------------

def test_num_ctx_fallback_chain_to_ollama_then_default() -> None:
    saved = _clear_num_ctx_env()
    try:
        # Sub-case 1: only OLLAMA_NUM_CTX set — both constants pick it up
        os.environ["OLLAMA_NUM_CTX"] = "2000"
        cfg = _reload_config()
        assert cfg.GENERAL_NUM_CTX == 2000, \
            f"GENERAL_NUM_CTX should equal OLLAMA_NUM_CTX=2000, got {cfg.GENERAL_NUM_CTX}"
        assert cfg.TRANSLATION_NUM_CTX == 2000, \
            f"TRANSLATION_NUM_CTX should equal OLLAMA_NUM_CTX=2000, got {cfg.TRANSLATION_NUM_CTX}"

        # Sub-case 2: no env vars set — hard defaults
        os.environ.pop("OLLAMA_NUM_CTX", None)
        cfg = _reload_config()
        assert cfg.GENERAL_NUM_CTX == 4096, \
            f"GENERAL_NUM_CTX default should be 4096, got {cfg.GENERAL_NUM_CTX}"
        assert cfg.TRANSLATION_NUM_CTX == 3072, \
            f"TRANSLATION_NUM_CTX default should be 3072, got {cfg.TRANSLATION_NUM_CTX}"
    finally:
        _restore_env(saved)
        _reload_config()


# ---------------------------------------------------------------------------
# AC-7: backward compat — only OLLAMA_NUM_CTX set
# ---------------------------------------------------------------------------

def test_only_ollama_num_ctx_set_backward_compat() -> None:
    saved = _clear_num_ctx_env()
    try:
        os.environ["OLLAMA_NUM_CTX"] = "3000"
        cfg = _reload_config()
        assert cfg.GENERAL_NUM_CTX == 3000, \
            f"GENERAL_NUM_CTX must equal OLLAMA_NUM_CTX=3000, got {cfg.GENERAL_NUM_CTX}"
        assert cfg.TRANSLATION_NUM_CTX == 3000, \
            f"TRANSLATION_NUM_CTX must equal OLLAMA_NUM_CTX=3000, got {cfg.TRANSLATION_NUM_CTX}"
    finally:
        _restore_env(saved)
        _reload_config()
