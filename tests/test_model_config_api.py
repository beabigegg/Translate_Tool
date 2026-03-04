"""Tests for model-config API and per-job num_ctx override handling."""

from __future__ import annotations

import importlib
import io
import sys
import types
from asyncio import run as run_async
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.datastructures import UploadFile

from app.backend.clients.ollama_client import OllamaClient
from app.backend.config import GENERAL_NUM_CTX, MODEL_TYPE_OPTIONS, TRANSLATION_NUM_CTX, ModelType


@pytest.fixture
def routes_module(monkeypatch):  # type: ignore[no-untyped-def]
    fake_job_manager_module = types.ModuleType("app.backend.services.job_manager")
    fake_python_multipart = types.ModuleType("python_multipart")
    fake_python_multipart.__version__ = "0.0.20"

    class FakeJobManager:
        def create_job(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            return SimpleNamespace(job_id="fake-job")

        def get_job(self, job_id):  # type: ignore[no-untyped-def]
            return None

        def cancel_job(self, job_id):  # type: ignore[no-untyped-def]
            return False

        def get_stats(self):  # type: ignore[no-untyped-def]
            return {}

    fake_job_manager_module.JobManager = FakeJobManager
    monkeypatch.setitem(sys.modules, "app.backend.services.job_manager", fake_job_manager_module)
    monkeypatch.setitem(sys.modules, "python_multipart", fake_python_multipart)
    sys.modules.pop("app.backend.api.routes", None)
    return importlib.import_module("app.backend.api.routes")


@pytest.fixture
def client(routes_module):  # type: ignore[no-untyped-def]
    app = FastAPI()
    app.include_router(routes_module.router, prefix="/api")
    return TestClient(app)


def _upload_file_obj() -> UploadFile:
    return UploadFile(filename="sample.docx", file=io.BytesIO(b"fake-docx-content"))


def test_model_config_endpoint_returns_all_model_types(client) -> None:  # type: ignore[no-untyped-def]
    response = client.get("/api/model-config")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)

    by_type = {item["model_type"]: item for item in payload}
    assert {"general", "translation"}.issubset(by_type.keys())

    assert by_type["general"]["default_num_ctx"] == GENERAL_NUM_CTX
    assert by_type["translation"]["default_num_ctx"] == TRANSLATION_NUM_CTX
    assert by_type["general"]["model_size_gb"] == 3.5
    assert by_type["translation"]["model_size_gb"] == 5.7


def test_create_job_rejects_out_of_range_num_ctx(routes_module, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    called = {"value": False}

    def _fake_create_job(*args, **kwargs):  # type: ignore[no-untyped-def]
        called["value"] = True
        return SimpleNamespace(job_id="should-not-create")

    monkeypatch.setattr(routes_module.job_manager, "create_job", _fake_create_job)
    with pytest.raises(HTTPException) as exc:
        run_async(
            routes_module.create_job(
                files=[_upload_file_obj()],
                targets="English",
                src_lang="auto",
                include_headers=False,
                profile="general",
                num_ctx=99999,
                pdf_output_format="pdf",
                pdf_layout_mode="overlay",
            )
        )

    assert exc.value.status_code == 422
    assert "num_ctx must be between" in str(exc.value.detail)
    assert called["value"] is False


def test_create_job_passes_valid_num_ctx_override(routes_module, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    captured: dict[str, object] = {}

    def _fake_create_job(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        return SimpleNamespace(job_id="job-123")

    monkeypatch.setattr(routes_module.job_manager, "create_job", _fake_create_job)
    response = run_async(
        routes_module.create_job(
            files=[_upload_file_obj()],
            targets="English",
            src_lang="auto",
            include_headers=False,
            profile="general",
            num_ctx=2048,
            pdf_output_format="pdf",
            pdf_layout_mode="overlay",
        )
    )

    assert response.job_id == "job-123"
    assert captured["num_ctx"] == 2048


def test_ollama_num_ctx_override_priority() -> None:
    client_with_override = OllamaClient(model_type=ModelType.TRANSLATION.value, num_ctx_override=2048)
    assert client_with_override._build_options()["num_ctx"] == 2048

    client_without_override = OllamaClient(model_type=ModelType.TRANSLATION.value)
    assert (
        client_without_override._build_options()["num_ctx"]
        == MODEL_TYPE_OPTIONS[ModelType.TRANSLATION]["num_ctx"]
    )
