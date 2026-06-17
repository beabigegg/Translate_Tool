"""Protocol conformance and source-integrity tests for LLMClient.

All tests in this file must FAIL before IP-1..IP-5 are implemented,
and pass after. Written per IP-0 in implementation-plan.md.
"""

from __future__ import annotations

import ast
import inspect
import re
from pathlib import Path
from typing import List, Optional, Tuple
import pytest

# Resolve repo root relative to this file
_REPO_ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# AC-1: base_llm_client.py defines LLMClient Protocol with exactly 6 methods
# ---------------------------------------------------------------------------

class TestProtocolDefinition:
    def test_protocol_defines_six_methods(self):
        """LLMClient Protocol must define exactly 6 methods."""
        from app.backend.clients.base_llm_client import LLMClient
        # Collect non-dunder methods defined on the Protocol
        methods = [
            name for name, member in inspect.getmembers(LLMClient)
            if not name.startswith("_")
            and callable(getattr(LLMClient, name, None))
        ]
        assert len(methods) == 6, f"Expected 6 Protocol methods, got {len(methods)}: {methods}"

    def test_protocol_method_signatures(self):
        """All 6 Protocol method signatures must match design.md table."""
        from app.backend.clients.base_llm_client import LLMClient

        sig_translate_once = inspect.signature(LLMClient.translate_once)
        params = list(sig_translate_once.parameters.keys())
        assert params == ["self", "text", "tgt", "src_lang"], f"translate_once params: {params}"

        sig_translate_batch = inspect.signature(LLMClient.translate_batch)
        params = list(sig_translate_batch.parameters.keys())
        assert params == ["self", "texts", "tgt", "src_lang"], f"translate_batch params: {params}"

        sig_refine = inspect.signature(LLMClient.refine_translation)
        params = list(sig_refine.parameters.keys())
        assert params == ["self", "source_text", "draft", "tgt", "src_lang"], f"refine_translation params: {params}"

        sig_health = inspect.signature(LLMClient.health)
        params = list(sig_health.parameters.keys())
        assert params == ["self"], f"health params: {params}"

        sig_list_models = inspect.signature(LLMClient.list_models)
        params = list(sig_list_models.parameters.keys())
        assert params == ["self"], f"list_models params: {params}"

        sig_unload = inspect.signature(LLMClient.unload)
        params = list(sig_unload.parameters.keys())
        assert params == ["self"], f"unload params: {params}"


# ---------------------------------------------------------------------------
# AC-2: OllamaClient is a structural subtype of LLMClient
# ---------------------------------------------------------------------------

class TestOllamaClientConformance:
    def test_ollama_client_satisfies_protocol(self):
        """OllamaClient must have all 6 Protocol methods."""
        from app.backend.clients.base_llm_client import LLMClient
        from app.backend.clients.ollama_client import OllamaClient

        for method_name in ["translate_once", "translate_batch", "refine_translation",
                             "health", "list_models", "unload"]:
            assert hasattr(OllamaClient, method_name), (
                f"OllamaClient missing Protocol method: {method_name}"
            )
            assert callable(getattr(OllamaClient, method_name)), (
                f"OllamaClient.{method_name} is not callable"
            )

    def test_ollama_client_isinstance_llm_client(self):
        """runtime_checkable isinstance must pass for OllamaClient instances."""
        from app.backend.clients.base_llm_client import LLMClient
        from app.backend.clients.ollama_client import OllamaClient

        client = OllamaClient()
        assert isinstance(client, LLMClient), (
            "OllamaClient() is not an instance of LLMClient Protocol"
        )


# ---------------------------------------------------------------------------
# AC-3: translation_service.py contains zero private calls
# ---------------------------------------------------------------------------

class TestNoPrivateCalls:
    def _read_translation_service(self) -> str:
        path = _REPO_ROOT / "app" / "backend" / "services" / "translation_service.py"
        return path.read_text()

    def test_translation_service_no_private_payload_call(self):
        """translation_service.py must contain zero calls to _build_no_system_payload."""
        src = self._read_translation_service()
        matches = re.findall(r'_build_no_system_payload', src)
        assert len(matches) == 0, (
            f"Found {len(matches)} call(s) to _build_no_system_payload in translation_service.py"
        )

    def test_translation_service_no_private_ollama_call(self):
        """translation_service.py must contain zero calls to _call_ollama."""
        src = self._read_translation_service()
        matches = re.findall(r'\._call_ollama\b', src)
        assert len(matches) == 0, (
            f"Found {len(matches)} call(s) to _call_ollama in translation_service.py"
        )


# ---------------------------------------------------------------------------
# AC-4: frozen public OllamaClient methods still present post-refactor
# ---------------------------------------------------------------------------

class TestOllamaClientFrozenPublicApi:
    def test_ollama_client_frozen_public_api_intact(self):
        """Frozen public methods must still exist on OllamaClient post-refactor."""
        from app.backend.clients.ollama_client import OllamaClient

        frozen_methods = [
            "health_check",
            "unload_model",
            "translate_once",
            "translate_batch",
            "refine_translation",
        ]
        for method_name in frozen_methods:
            assert hasattr(OllamaClient, method_name), (
                f"OllamaClient is missing frozen public method: {method_name}"
            )
            assert callable(getattr(OllamaClient, method_name)), (
                f"OllamaClient.{method_name} is not callable"
            )

    def test_ollama_client_alias_methods_delegate(self):
        """health(), list_models(), unload() must delegate to frozen behavior."""
        from unittest.mock import MagicMock, patch
        from app.backend.clients.ollama_client import OllamaClient

        client = OllamaClient()

        # health() delegates to health_check()
        with patch.object(client, "health_check", return_value=(True, "OK")) as mock_hc:
            result = client.health()
            mock_hc.assert_called_once()
            assert result == (True, "OK")

        # unload() delegates to unload_model()
        with patch.object(client, "unload_model", return_value=(True, "unloaded")) as mock_um:
            result = client.unload()
            mock_um.assert_called_once()
            assert result == (True, "unloaded")

        # list_models() delegates to list_ollama_models (module-level function)
        with patch("app.backend.clients.ollama_client.list_ollama_models", return_value=["model-a"]) as mock_lm:
            result = client.list_models()
            mock_lm.assert_called_once_with(client.base_url)
            assert result == ["model-a"]


# ---------------------------------------------------------------------------
# AC-5: context-detection uses public Protocol method
# ---------------------------------------------------------------------------

class TestContextDetectionPublicMethod:
    def test_context_detection_uses_public_method(self):
        """translate_texts deferred-context-detection must use a public Protocol method."""
        from unittest.mock import MagicMock, patch
        from app.backend.clients.ollama_client import OllamaClient
        from app.backend.services.translation_service import translate_texts

        primary = MagicMock(spec=OllamaClient)
        primary.model = "hymt-model"
        primary.cache_model_key = "hymt-model"

        refiner = MagicMock(spec=OllamaClient)
        refiner.model = "qwen-model"
        refiner.cache_model_key = "qwen-model"
        refiner.refine_translation.return_value = (True, "refined")

        # Set deferred_context_sample to trigger the detection block
        refiner._deferred_context_sample = "sample document text for context detection"
        refiner._deferred_context_profile = "general"
        refiner._deferred_context_target = "Vietnamese"

        # The detection call should use a public Protocol method — we verify by confirming
        # that at least one public method on refiner is called during context detection.
        # Specifically: translate_once should be called for detection.
        refiner.translate_once.return_value = (True, "這是技術文件，涉及工業製程。")

        long_text = "A" * 50  # long enough to trigger refinement

        with patch("app.backend.services.translation_service.CROSS_MODEL_REFINEMENT_ENABLED", True), \
             patch("app.backend.services.translation_service.get_cache", return_value=None), \
             patch("app.backend.services.translation_service.translate_blocks_batch",
                   return_value=[(True, "B" * 50)]):
            translate_texts(
                texts=[long_text],
                targets=["Vietnamese"],
                src_lang="English",
                client=primary,
                refine_client=refiner,
            )

        # The detection block must have called a public Protocol method
        # (translate_once) rather than private _build_no_system_payload/_call_ollama
        refiner.translate_once.assert_called()


# ---------------------------------------------------------------------------
# AC-6: base_llm_client.py imports only stdlib typing
# ---------------------------------------------------------------------------

class TestBaseModuleStdlibOnly:
    def test_base_module_stdlib_only(self):
        """base_llm_client.py must import only stdlib typing (no third-party)."""
        path = _REPO_ROOT / "app" / "backend" / "clients" / "base_llm_client.py"
        source = path.read_text()
        tree = ast.parse(source)

        third_party_prefixes = ("requests", "flask", "opencc", "urllib3")
        allowed_stdlib_modules = {"__future__", "typing"}

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_module = alias.name.split(".")[0]
                    assert root_module in allowed_stdlib_modules or root_module.startswith("_"), (
                        f"base_llm_client.py imports non-stdlib module: {alias.name}"
                    )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root_module = node.module.split(".")[0]
                    assert root_module in allowed_stdlib_modules or root_module.startswith("_"), (
                        f"base_llm_client.py imports from non-stdlib module: {node.module}"
                    )


# ---------------------------------------------------------------------------
# AC-7: no governed contract file is modified (source check)
# ---------------------------------------------------------------------------

class TestNoGovernedContractModified:
    def test_no_governed_contract_modified(self):
        """Governed contract files must not be modified by this change.

        Checks that the contract directory paths exist and that key contract
        files do not contain any LLMClient Protocol source (which would
        indicate they were incorrectly modified).
        """
        contracts_root = _REPO_ROOT / "contracts"
        governed_files = [
            contracts_root / "api" / "api-contract.md",
            contracts_root / "business" / "business-rules.md",
            contracts_root / "data" / "data-shape-contract.md",
            contracts_root / "env" / "env-contract.md",
        ]
        for path in governed_files:
            assert path.exists(), f"Governed contract file missing: {path}"
            content = path.read_text()
            # LLMClient Protocol definition should NOT appear in contract files
            assert "class LLMClient(Protocol)" not in content, (
                f"LLMClient Protocol definition found in governed contract: {path}"
            )
