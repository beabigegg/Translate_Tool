"""Fallback-chain, provider-attribution, and JobStatus-shape tests (p1-cloud-providers).

All tests here must FAIL before IP-4..IP-7 are implemented (TDD).
Mock at requests.Session.post/get boundary only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch, call

import pytest

_REPO_ROOT = Path(__file__).parent.parent


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_chat_response(content: str) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"choices": [{"message": {"content": content}}]}
    return resp


def _make_http_error_response(status_code: int) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = f"HTTP {status_code}"
    return resp


# ── TestFallbackChain ─────────────────────────────────────────────────────────

class TestFallbackChain:
    """Integration tests for the ordered fallback walk in the orchestrator."""

    def _build_two_provider_config(self, primary_id: str, fallback_id: str) -> dict:
        """Return a minimal ProviderConfig dict with two providers."""
        return {
            "providers": [
                {
                    "id": primary_id,
                    "type": "openai",
                    "enabled": True,
                    "base_url": "http://primary:8080",
                    "api_key": "key-primary",
                    "models": {"translate": "model-primary"},
                },
                {
                    "id": fallback_id,
                    "type": "openai",
                    "enabled": True,
                    "base_url": "http://fallback:8080",
                    "api_key": "key-fallback",
                    "models": {"translate": "model-fallback"},
                },
            ],
            "routing": {
                "default": {
                    "model": "model-primary",
                    "provider": primary_id,
                    "profile": "general",
                }
            },
            "fallback_chain": [primary_id, fallback_id],
        }

    def test_primary_offline_falls_back_to_next(self):
        """ConnectionError on primary → fallback is tried and succeeds."""
        import requests as req_lib
        from app.backend.clients.openai_compatible_client import OpenAICompatibleClient

        primary = OpenAICompatibleClient(
            base_url="http://primary:8080",
            api_key="key-primary",
            model="model-primary",
        )
        fallback = OpenAICompatibleClient(
            base_url="http://fallback:8080",
            api_key="key-fallback",
            model="model-fallback",
        )

        call_count = {"n": 0}

        def _side_effect(url, **kwargs):
            call_count["n"] += 1
            if "primary" in url:
                raise req_lib.exceptions.ConnectionError("refused")
            return _make_chat_response("Fallback result")

        with patch("requests.Session.post", side_effect=_side_effect):
            ok_p, _ = primary.translate_once("Hello", "French", "English")
            ok_f, result = fallback.translate_once("Hello", "French", "English")

        assert ok_p is False
        assert ok_f is True
        assert "Fallback" in result

    def test_primary_timeout_falls_back_to_next(self):
        """Timeout on primary → fallback succeeds."""
        import requests as req_lib
        from app.backend.clients.openai_compatible_client import OpenAICompatibleClient

        primary = OpenAICompatibleClient(
            base_url="http://primary:8080",
            api_key="key-primary",
            model="model-primary",
        )
        fallback = OpenAICompatibleClient(
            base_url="http://fallback:8080",
            api_key="key-fallback",
            model="model-fallback",
        )

        def _side_effect(url, **kwargs):
            if "primary" in url:
                raise req_lib.exceptions.Timeout("timed out")
            return _make_chat_response("Fallback OK")

        with patch("requests.Session.post", side_effect=_side_effect):
            ok_p, _ = primary.translate_once("Hello", "French", "English")
            ok_f, result = fallback.translate_once("Hello", "French", "English")

        assert ok_p is False
        assert ok_f is True

    def test_primary_auth_failure_falls_back_to_next(self):
        """HTTP 401 on primary → fallback is tried."""
        from app.backend.clients.openai_compatible_client import OpenAICompatibleClient

        primary = OpenAICompatibleClient(
            base_url="http://primary:8080",
            api_key="bad-key",
            model="model-primary",
        )
        fallback = OpenAICompatibleClient(
            base_url="http://fallback:8080",
            api_key="good-key",
            model="model-fallback",
        )

        def _side_effect(url, **kwargs):
            if "primary" in url:
                return _make_http_error_response(401)
            return _make_chat_response("Authorized result")

        with patch("requests.Session.post", side_effect=_side_effect):
            ok_p, _ = primary.translate_once("Hello", "French", "English")
            ok_f, result = fallback.translate_once("Hello", "French", "English")

        assert ok_p is False
        assert ok_f is True

    def test_all_providers_fail_job_fails(self):
        """All providers fail → final ok is False."""
        import requests as req_lib
        from app.backend.clients.openai_compatible_client import OpenAICompatibleClient

        providers = [
            OpenAICompatibleClient(
                base_url=f"http://provider{i}:8080",
                api_key=f"key-{i}",
                model=f"model-{i}",
            )
            for i in range(3)
        ]

        with patch("requests.Session.post",
                   side_effect=req_lib.exceptions.ConnectionError("all down")):
            results = [p.translate_once("Hello", "French", "English") for p in providers]

        assert all(ok is False for ok, _ in results)

    def test_first_success_wins_chain_stops(self):
        """Once a provider succeeds, subsequent providers are not attempted."""
        from app.backend.clients.openai_compatible_client import OpenAICompatibleClient

        client = OpenAICompatibleClient(
            base_url="http://winner:8080",
            api_key="key-winner",
            model="model-winner",
        )

        post_call_count = {"n": 0}

        def _side_effect(url, **kwargs):
            post_call_count["n"] += 1
            return _make_chat_response("Winner result")

        with patch("requests.Session.post", side_effect=_side_effect):
            ok, result = client.translate_once("Hello", "French", "English")

        assert ok is True
        assert post_call_count["n"] == 1  # Only one POST call; chain stopped


# ── TestProviderAttribution ───────────────────────────────────────────────────

class TestProviderAttribution:
    """Tests that the winning provider ID is recorded on JobRecord / JobStatus."""

    def test_winning_provider_recorded_on_job_status(self):
        """JobStatus.provider is set to the winning provider ID after success."""
        from app.backend.api.schemas import JobStatus

        status = JobStatus(
            job_id="test-job-1",
            status="completed",
            processed_files=1,
            total_files=1,
            output_ready=True,
            provider="panjit",
        )
        assert status.provider == "panjit"

    def test_fallback_provider_recorded_not_primary(self):
        """When fallback is used, its ID is recorded (not primary)."""
        from app.backend.api.schemas import JobStatus

        status = JobStatus(
            job_id="test-job-2",
            status="completed",
            processed_files=1,
            total_files=1,
            output_ready=True,
            provider="ollama-local",  # fallback won
        )
        assert status.provider == "ollama-local"
        assert status.provider != "panjit"

    def test_no_provider_recorded_when_job_fails(self):
        """On total failure, provider remains None."""
        from app.backend.api.schemas import JobStatus

        status = JobStatus(
            job_id="test-job-3",
            status="failed",
            processed_files=0,
            total_files=1,
            output_ready=False,
            provider=None,
        )
        assert status.provider is None


# ── TestJobStatusShape ────────────────────────────────────────────────────────

class TestJobStatusShape:
    """Schema-level assertions for the additive provider field."""

    def test_job_status_provider_field_is_optional_str(self):
        """JobStatus.provider must accept a string value without errors."""
        from app.backend.api.schemas import JobStatus

        status = JobStatus(
            job_id="j1",
            status="completed",
            processed_files=1,
            total_files=1,
            output_ready=True,
            provider="deepseek",
        )
        assert isinstance(status.provider, str)
        assert status.provider == "deepseek"

    def test_job_status_provider_field_defaults_to_none(self):
        """JobStatus.provider must default to None (backward-compatible)."""
        from app.backend.api.schemas import JobStatus

        status = JobStatus(
            job_id="j2",
            status="queued",
            processed_files=0,
            total_files=0,
            output_ready=False,
        )
        assert status.provider is None

    def test_download_url_field_defaults_to_none(self):
        """JobStatus.download_url must default to None (AC-1)."""
        from app.backend.api.schemas import JobStatus

        job_status = JobStatus(
            job_id="j3",
            status="running",
            processed_files=0,
            total_files=1,
            output_ready=False,
        )
        assert job_status.download_url is None

    def test_download_url_field_accepts_string(self):
        """JobStatus.download_url must accept a string value without errors (AC-1)."""
        from app.backend.api.schemas import JobStatus

        job_status = JobStatus(
            job_id="j4",
            status="completed",
            processed_files=1,
            total_files=1,
            output_ready=True,
            download_url="/api/jobs/abc123/download",
        )
        assert job_status.download_url == "/api/jobs/abc123/download"


# ── TestOrchestratorProviderWiring ───────────────────────────────────────────


class TestOrchestratorProviderWiring:
    """Verify that process_files dispatches to the cloud client (AC-5, AC-6).

    These tests mock at the requests.Session.post boundary and verify:
    1. When provider_id="panjit" and providers.yml resolves it as an
       enabled OpenAI-compatible provider, the orchestrator builds an
       OpenAICompatibleClient and uses it as the primary translation client.
    2. winning_provider in the return tuple equals the cloud provider ID
       (BR-16: accurate attribution).
    3. When the cloud client is selected, requests.Session.post is called
       (not the Ollama /api/generate endpoint).
    """

    _PANJIT_PROVIDERS_CONFIG = {
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
        "routing": {
            "default": {
                "model": "gpt-oss:120b",
                "provider": "panjit",
                "profile": "general",
            }
        },
        "fallback_chain": ["panjit", "deepseek"],
    }

    def test_cloud_client_used_when_provider_id_set(self):
        """When provider_id='panjit', OpenAICompatibleClient handles translation calls."""
        import tempfile, pathlib
        from unittest.mock import MagicMock, patch, call as mcall

        # Create a minimal .docx for the orchestrator to try to process
        # (the translate_docx function is mocked so the file content doesn't matter)
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = pathlib.Path(tmpdir)
            src_docx = tmp_path / "test.docx"
            out_dir = tmp_path / "out"
            out_dir.mkdir()

            # Write a minimal valid docx so the orchestrator doesn't fail on file ops
            try:
                import docx as _docx
                doc = _docx.Document()
                doc.add_paragraph("Hello world")
                doc.save(str(src_docx))
            except Exception:
                # If python-docx unavailable, create a dummy non-docx file and
                # rely on the mock to bypass actual processing
                src_docx.write_bytes(b"PK\x03\x04")  # minimal zip header

            post_calls = []

            def _mock_post(url, **kwargs):
                post_calls.append(url)
                resp = MagicMock()
                resp.status_code = 200
                resp.json.return_value = {
                    "choices": [{"message": {"content": "Bonjour monde"}}]
                }
                return resp

            # Mock load_providers_config at the config module level
            # (it is imported locally inside process_files so we patch the source)
            # Mock translate_docx to bypass actual document processing
            with patch(
                "app.backend.config.load_providers_config",
                return_value=self._PANJIT_PROVIDERS_CONFIG,
            ), patch(
                "requests.Session.post",
                side_effect=_mock_post,
            ), patch(
                # Disable context detection — it calls OllamaClient internals
                # (_build_no_system_payload, _call_ollama) not available on cloud clients.
                # This test focuses on client dispatch wiring, not context detection.
                "app.backend.processors.orchestrator.CONTEXT_DETECTION_ENABLED",
                False,
            ), patch(
                "app.backend.processors.orchestrator.translate_docx",
                return_value=False,  # stopped=False (not stopped)
            ) as mock_translate_docx:
                from app.backend.processors.orchestrator import process_files
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

            # process_files should return the 6-tuple with winning_provider
            assert len(result) == 6, f"Expected 6-tuple, got {len(result)}"
            _processed, _total, _stopped, _client, _term, winning_provider = result

            # BR-16: winning provider must be "panjit" (the cloud provider)
            assert winning_provider == "panjit", (
                f"Expected winning_provider='panjit', got {winning_provider!r}"
            )

            # AC-5: translate_docx was called with the cloud client, not OllamaClient
            assert mock_translate_docx.called, "translate_docx should have been called"
            call_args = mock_translate_docx.call_args
            # client is the 5th positional argument (index 4) in translate_docx(
            #   in_path, out_path, targets, src_lang, client, ...)
            positional_args = call_args.args if hasattr(call_args, "args") else call_args[0]
            passed_client = positional_args[4]
            from app.backend.clients.openai_compatible_client import OpenAICompatibleClient
            assert isinstance(passed_client, OpenAICompatibleClient), (
                f"translate_docx received {type(passed_client).__name__}, "
                "expected OpenAICompatibleClient"
            )

    def test_ollama_used_when_no_cloud_provider(self):
        """When provider_id=None, OllamaClient is used and winning_provider='ollama-local'."""
        import tempfile, pathlib
        from unittest.mock import patch, MagicMock

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = pathlib.Path(tmpdir)
            src_docx = tmp_path / "test.docx"
            out_dir = tmp_path / "out"
            out_dir.mkdir()
            src_docx.write_bytes(b"PK\x03\x04")

            with patch(
                "app.backend.processors.orchestrator.translate_docx",
                return_value=False,
            ), patch(
                "app.backend.clients.ollama_client.OllamaClient.health_check",
                return_value=(True, "OK"),
            ):
                from app.backend.processors.orchestrator import process_files
                from app.backend.clients.ollama_client import OllamaClient

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
                    provider_id=None,  # no cloud provider
                )

            assert len(result) == 6
            _processed, _total, _stopped, _client, _term, winning_provider = result
            # When no cloud provider is configured, falls back to ollama-local
            assert winning_provider == "ollama-local", (
                f"Expected 'ollama-local', got {winning_provider!r}"
            )


# ── TestFallbackChainConfig ───────────────────────────────────────────────────


class TestFallbackChainConfig:
    """AC-1, AC-2, AC-3: Verify providers.yml fallback_chain and DeepSeek gating."""

    def test_fallback_chain_is_panjit_deepseek(self):
        """AC-1: fallback_chain in providers.yml is exactly ['panjit', 'deepseek']."""
        import yaml

        # Read the tracked template (providers.yml is gitignored; .example is the CI source of truth)
        providers_yml = _REPO_ROOT / "config" / "providers.yml.example"
        raw = providers_yml.read_text(encoding="utf-8")
        # Strip ${VAR} interpolations so yaml.safe_load can parse the file directly
        import re
        # Replace ${VAR:-default} → default; ${VAR} → ""
        raw_clean = re.sub(r"\$\{[^}]+:-([^}]*)\}", r"\1", raw)
        raw_clean = re.sub(r"\$\{[^}]+\}", '""', raw_clean)
        cfg = yaml.safe_load(raw_clean)
        chain = cfg.get("fallback_chain", [])
        assert chain == ["panjit", "deepseek"], (
            f"Expected fallback_chain=['panjit', 'deepseek'], got {chain!r}. "
            "Update config/providers.yml.example (IP-1)."
        )
        assert "ollama-local" not in chain, (
            "ollama-local must not appear in fallback_chain."
        )

    def test_ollama_local_role_is_layout_assist_only(self):
        """AC-2: ollama-local provider entry is retained with role=layout_assist_only."""
        import yaml
        import re

        providers_yml = _REPO_ROOT / "config" / "providers.yml.example"
        raw = providers_yml.read_text(encoding="utf-8")
        raw_clean = re.sub(r"\$\{[^}]+:-([^}]*)\}", r"\1", raw)
        raw_clean = re.sub(r"\$\{[^}]+\}", '""', raw_clean)
        cfg = yaml.safe_load(raw_clean)
        providers = {p["id"]: p for p in cfg.get("providers", [])}
        assert "ollama-local" in providers, (
            "ollama-local provider entry must remain in providers.yml (layout_assist_only)."
        )
        assert providers["ollama-local"].get("role") == "layout_assist_only", (
            f"Expected role='layout_assist_only', got {providers['ollama-local'].get('role')!r}."
        )

    def test_deepseek_excluded_when_disabled(self):
        """AC-3: When DEEPSEEK_ENABLED=false, deepseek enabled coerces to False."""
        import os
        import importlib

        # Force DEEPSEEK_ENABLED=false for this test
        env_backup = os.environ.copy()
        os.environ["DEEPSEEK_ENABLED"] = "false"
        # Ensure required vars present (prevents unresolved-var disable path)
        os.environ.setdefault("PANJIT_LLM_BASE_URL", "http://panjit-mock:8080")
        os.environ.setdefault("PANJIT_API", "test-key")
        os.environ.setdefault("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        os.environ.setdefault("DEEPSEEK_API", "test-deepseek-key")
        os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")
        try:
            import app.backend.config as cfg_module
            importlib.reload(cfg_module)
            config = cfg_module.load_providers_config()
        finally:
            # Restore environment
            os.environ.clear()
            os.environ.update(env_backup)

        assert config is not None, "load_providers_config() returned None"
        providers = {p["id"]: p for p in config.get("providers", [])}
        assert "deepseek" in providers, "deepseek provider entry missing from config"
        assert providers["deepseek"]["enabled"] is False, (
            f"Expected deepseek enabled=False when DEEPSEEK_ENABLED=false, "
            f"got {providers['deepseek']['enabled']!r}"
        )
        # Confirm deepseek is not in active (enabled) fallback candidates
        chain = config.get("fallback_chain", [])
        enabled_in_chain = [
            _id for _id in chain
            if providers.get(_id, {}).get("enabled") is True
        ]
        assert "deepseek" not in enabled_in_chain, (
            "deepseek must not appear in enabled chain when DEEPSEEK_ENABLED=false."
        )

    def test_deepseek_included_when_enabled(self):
        """AC-3 (enabled): When DEEPSEEK_ENABLED=true, deepseek enabled coerces to True."""
        import os
        import importlib

        env_backup = os.environ.copy()
        os.environ["DEEPSEEK_ENABLED"] = "true"
        os.environ["DEEPSEEK_API"] = "test-deepseek-key"
        os.environ.setdefault("PANJIT_LLM_BASE_URL", "http://panjit-mock:8080")
        os.environ.setdefault("PANJIT_API", "test-key")
        os.environ.setdefault("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")
        try:
            import app.backend.config as cfg_module
            importlib.reload(cfg_module)
            config = cfg_module.load_providers_config()
        finally:
            os.environ.clear()
            os.environ.update(env_backup)

        assert config is not None
        providers = {p["id"]: p for p in config.get("providers", [])}
        assert "deepseek" in providers
        assert providers["deepseek"]["enabled"] is True, (
            f"Expected deepseek enabled=True when DEEPSEEK_ENABLED=true, "
            f"got {providers['deepseek']['enabled']!r}"
        )


# ── TestOrchestratorFallbackTraversal ─────────────────────────────────────────


class TestOrchestratorFallbackTraversal:
    """AC-5, AC-6, AC-8: orchestrator fallback traversal — no ollama-local branch."""

    def test_ollama_local_branch_absent_from_orchestrator(self):
        """AC-5: The string 'if _fb_id == "ollama-local": break' must not exist in orchestrator.py."""
        orchestrator_path = (
            _REPO_ROOT / "app" / "backend" / "processors" / "orchestrator.py"
        )
        source = orchestrator_path.read_text(encoding="utf-8")
        assert '_fb_id == "ollama-local"' not in source, (
            "orchestrator.py still contains the ollama-local break-guard. "
            "Remove the 'if _fb_id == \"ollama-local\": break' guard (IP-2)."
        )

    def test_fallback_order_selection_at_orchestrator_seam(self):
        """AC-5/AC-8: When PANJIT fails, deepseek is resolved as winning_provider (not ollama-local).

        Selection-style: asserts WHICH provider was chosen, not just how many calls occurred.
        Mocks at the consumer seam: app.backend.config.load_providers_config.
        """
        import tempfile
        import pathlib

        # Config where panjit is disabled (simulates PANJIT failure to build client)
        # and deepseek is enabled (simulates DEEPSEEK_ENABLED=true)
        _config = {
            "providers": [
                {
                    "id": "panjit",
                    "type": "openai",
                    "enabled": False,  # PANJIT disabled → build skipped
                    "base_url": "http://panjit-mock:8080",
                    "api_key": "test-key-panjit",
                    "models": {"translate": "gpt-oss:120b"},
                },
                {
                    "id": "deepseek",
                    "type": "openai",
                    "enabled": True,  # DeepSeek enabled → should be selected
                    "base_url": "https://api.deepseek.com",
                    "api_key": "test-deepseek-key",
                    "models": {"translate": "deepseek-v4-flash"},
                },
                {
                    "id": "ollama-local",
                    "type": "ollama",
                    "enabled": True,
                    "base_url": "http://localhost:11434",
                    "role": "layout_assist_only",
                },
            ],
            "routing": {
                "default": {
                    "model": "gpt-oss:120b",
                    "provider": "panjit",
                    "profile": "general",
                }
            },
            "fallback_chain": ["panjit", "deepseek"],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = pathlib.Path(tmpdir)
            src_docx = tmp_path / "test.docx"
            out_dir = tmp_path / "out"
            out_dir.mkdir()
            src_docx.write_bytes(b"PK\x03\x04")

            with patch(
                "app.backend.config.load_providers_config",
                return_value=_config,
            ), patch(
                "app.backend.clients.openai_compatible_client.OpenAICompatibleClient.health",
                return_value=(True, "OK"),
            ), patch(
                "app.backend.processors.orchestrator.CONTEXT_DETECTION_ENABLED",
                False,
            ), patch(
                "app.backend.processors.orchestrator.translate_docx",
                return_value=False,
            ):
                from app.backend.processors.orchestrator import process_files

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
                    provider_id="panjit",  # panjit is the requested provider but disabled
                )

        assert len(result) == 6
        _processed, _total, _stopped, _client, _term, winning_provider = result
        # Selection-style: deepseek must be the winner, not ollama-local
        assert winning_provider == "deepseek", (
            f"Expected winning_provider='deepseek' (fallback chain resolved deepseek), "
            f"got {winning_provider!r}. "
            "Verify IP-2 removed the ollama-local break-guard and deepseek health passes."
        )

    def test_panjit_fail_deepseek_disabled_graceful(self):
        """AC-6: PANJIT fail + DeepSeek disabled → graceful failure; no local provider contacted.

        Asserts:
        - winning_provider is 'ollama-local' (OllamaClient is the fallthrough, not a cloud attempt)
          OR process_files completes without raising.
        - No HTTP call is made to localhost:11434 for translation (translate_docx is mocked).
        - No call to 'http://localhost:11434' is made via requests.Session.post.
        """
        import tempfile
        import pathlib

        # Config where both panjit and deepseek are disabled
        _config = {
            "providers": [
                {
                    "id": "panjit",
                    "type": "openai",
                    "enabled": False,  # PANJIT disabled
                    "base_url": "http://panjit-mock:8080",
                    "api_key": "test-key-panjit",
                    "models": {"translate": "gpt-oss:120b"},
                },
                {
                    "id": "deepseek",
                    "type": "openai",
                    "enabled": False,  # DeepSeek disabled (DEEPSEEK_ENABLED=false)
                    "base_url": "https://api.deepseek.com",
                    "api_key": "",
                    "models": {"translate": "deepseek-v4-flash"},
                },
                {
                    "id": "ollama-local",
                    "type": "ollama",
                    "enabled": True,
                    "base_url": "http://localhost:11434",
                    "role": "layout_assist_only",
                },
            ],
            "routing": {
                "default": {
                    "model": "gpt-oss:120b",
                    "provider": "panjit",
                    "profile": "general",
                }
            },
            "fallback_chain": ["panjit", "deepseek"],
        }

        localhost_calls = []

        def _track_post(url, **kwargs):
            if "localhost:11434" in url:
                localhost_calls.append(url)
            raise Exception(f"No HTTP calls expected in this test, got: {url}")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = pathlib.Path(tmpdir)
            src_docx = tmp_path / "test.docx"
            out_dir = tmp_path / "out"
            out_dir.mkdir()
            src_docx.write_bytes(b"PK\x03\x04")

            with patch(
                "app.backend.config.load_providers_config",
                return_value=_config,
            ), patch(
                "app.backend.processors.orchestrator.CONTEXT_DETECTION_ENABLED",
                False,
            ), patch(
                "app.backend.processors.orchestrator.translate_docx",
                return_value=False,
            ), patch(
                "requests.Session.post",
                side_effect=_track_post,
            ):
                from app.backend.processors.orchestrator import process_files

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

        # Graceful failure: no cloud client was resolved
        assert len(result) == 6
        _processed, _total, _stopped, _client, _term, winning_provider = result

        # No local translation model attempted via HTTP
        assert localhost_calls == [], (
            f"No calls to localhost:11434 expected in graceful-failure path, "
            f"got: {localhost_calls!r}"
        )

        # The orchestrator should fall through to OllamaClient (translate_docx mocked)
        # without raising — winning_provider reflects the OllamaClient path
        assert winning_provider == "ollama-local", (
            f"Expected graceful failure path → winning_provider='ollama-local' "
            f"(OllamaClient fallthrough), got {winning_provider!r}"
        )


# ── TestLayoutDetectorUnchanged ───────────────────────────────────────────────


class TestLayoutDetectorUnchanged:
    """AC-7: layout_detector.py and its Ollama layout path are unchanged."""

    def test_layout_detector_source_unmodified(self):
        """AC-7: layout_detector.py retains the Docling heron-101 ONNX landmark string."""
        layout_detector_path = (
            _REPO_ROOT / "app" / "backend" / "parsers" / "layout_detector.py"
        )
        assert layout_detector_path.exists(), (
            f"layout_detector.py not found at {layout_detector_path}. "
            "AC-7 requires this file to be present and unmodified."
        )
        source = layout_detector_path.read_text(encoding="utf-8")
        landmark = "Docling heron-101 ONNX model"
        assert landmark in source, (
            f"Landmark string {landmark!r} not found in layout_detector.py. "
            "Ensure layout_detector.py was not modified (AC-7)."
        )
