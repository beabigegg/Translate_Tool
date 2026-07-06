"""Tests for LibreOffice-headless conversion helpers (support-legacy-office-formats).

Covers:
- AC-1: ppt_to_pptx() converts .ppt -> .pptx, signature/error parity with doc_to_docx().
- AC-2: .ppt is in SUPPORTED_EXTENSIONS.
- AC-3: doc_to_docx() / xls_to_xlsx() conversion helpers (previously untested).
- AC-4: is_libreoffice_available() true/false branches.

Anti-tautology / determinism (per implementation-plan.md, ci-gates.md):
- shutil.which and subprocess.Popen are mocked for every test in this file —
  the real LibreOffice binary is never required for CI determinism.
- Conversion tests assert on the ACTUAL converted-file bytes reaching
  output_path (selection assertion), not merely that subprocess.Popen was called.

Process-group timeout fix (fix(libreoffice): kill whole process tree on
timeout, not just the direct child — see _libreoffice_convert):
- /usr/bin/soffice forks soffice.bin rather than exec-replacing itself, so
  subprocess.run(timeout=...)'s default kill only reaped the direct child and
  left soffice.bin running indefinitely (observed: 10+ hours at 100% CPU on a
  pathological .doc). _libreoffice_convert now uses subprocess.Popen with
  start_new_session=True + os.killpg on TimeoutExpired.
"""

from __future__ import annotations

import inspect
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.backend.processors import libreoffice_helpers as lo


@pytest.fixture(autouse=True)
def _reset_binary_cache():
    """Reset the module-level LibreOffice detection cache around every test."""
    lo._LIBREOFFICE_BINARY = None
    lo._DETECTION_DONE = False
    yield
    lo._LIBREOFFICE_BINARY = None
    lo._DETECTION_DONE = False


class _FakePopen:
    """Simulate a successful LibreOffice --convert-to invocation via Popen.

    Writes a real output file named <input-stem>.<target-format> into --outdir,
    matching what _libreoffice_convert expects to find afterward.
    """

    def __init__(self, cmd, stdout=None, stderr=None, text=None, start_new_session=None):
        self.cmd = cmd
        self.pid = 99999
        self.returncode = 0
        outdir = cmd[cmd.index("--outdir") + 1]
        input_path = cmd[-1]
        target_format = cmd[cmd.index("--convert-to") + 1]
        stem = Path(input_path).stem
        Path(outdir, f"{stem}.{target_format}").write_bytes(b"converted-bytes")

    def communicate(self, timeout=None):
        return ("", "")


# ---------------------------------------------------------------------------
# AC-4: is_libreoffice_available()
# ---------------------------------------------------------------------------

def test_is_libreoffice_available_true_when_binary_found():
    """AC-4: shutil.which finding 'soffice' on PATH makes is_libreoffice_available() True."""
    with patch(
        "shutil.which",
        side_effect=lambda name: "/usr/bin/soffice" if name == "soffice" else None,
    ):
        assert lo.is_libreoffice_available() is True


def test_is_libreoffice_available_false_when_no_binary_found():
    """AC-4: no PATH match and no common install path match -> False, no crash."""
    with (
        patch("shutil.which", return_value=None),
        patch("os.path.isfile", return_value=False),
    ):
        assert lo.is_libreoffice_available() is False


# ---------------------------------------------------------------------------
# AC-3: doc_to_docx / xls_to_xlsx (previously-untested legacy helpers)
# ---------------------------------------------------------------------------

def test_doc_to_docx_converts_via_subprocess(tmp_path):
    """AC-3: doc_to_docx() drives subprocess.run and moves the converted file to output_path."""
    input_path = tmp_path / "in.doc"
    input_path.write_bytes(b"fake-doc-bytes")
    output_path = tmp_path / "out.docx"

    with (
        patch(
            "shutil.which",
            side_effect=lambda name: "/usr/bin/soffice" if name == "soffice" else None,
        ),
        patch("subprocess.Popen", side_effect=_FakePopen) as mock_run,
    ):
        lo.doc_to_docx(str(input_path), str(output_path))

    assert mock_run.called, "subprocess.run must be invoked for LibreOffice conversion"
    assert output_path.exists(), "doc_to_docx must produce the requested output_path"
    assert output_path.read_bytes() == b"converted-bytes"


def test_xls_to_xlsx_converts_via_subprocess(tmp_path):
    """AC-3: xls_to_xlsx() drives subprocess.run and moves the converted file to output_path."""
    input_path = tmp_path / "in.xls"
    input_path.write_bytes(b"fake-xls-bytes")
    output_path = tmp_path / "out.xlsx"

    with (
        patch(
            "shutil.which",
            side_effect=lambda name: "/usr/bin/soffice" if name == "soffice" else None,
        ),
        patch("subprocess.Popen", side_effect=_FakePopen) as mock_run,
    ):
        lo.xls_to_xlsx(str(input_path), str(output_path))

    assert mock_run.called, "subprocess.run must be invoked for LibreOffice conversion"
    assert output_path.exists(), "xls_to_xlsx must produce the requested output_path"
    assert output_path.read_bytes() == b"converted-bytes"


# ---------------------------------------------------------------------------
# AC-1 / AC-2: ppt_to_pptx (new)
# ---------------------------------------------------------------------------

def test_ppt_to_pptx_converts_when_libreoffice_available(tmp_path):
    """AC-1: ppt_to_pptx() produces a .pptx at output_path via a mocked LibreOffice convert."""
    input_path = tmp_path / "in.ppt"
    input_path.write_bytes(b"fake-ppt-bytes")
    output_path = tmp_path / "out.pptx"

    with (
        patch(
            "shutil.which",
            side_effect=lambda name: "/usr/bin/soffice" if name == "soffice" else None,
        ),
        patch("subprocess.Popen", side_effect=_FakePopen) as mock_run,
    ):
        lo.ppt_to_pptx(str(input_path), str(output_path))

    assert mock_run.called, "subprocess.run must be invoked for LibreOffice conversion"
    assert output_path.exists(), "ppt_to_pptx must produce the requested output_path"
    assert output_path.read_bytes() == b"converted-bytes"


def test_ppt_to_pptx_signature_and_error_semantics_match_doc_to_docx(tmp_path):
    """AC-1: ppt_to_pptx() mirrors doc_to_docx() signature and unavailable-binary error semantics.

    Anti-tautology: asserts on the EXACT parameter names/order (selection assertion),
    not merely that both functions are callable.
    """
    sig_doc = inspect.signature(lo.doc_to_docx)
    sig_ppt = inspect.signature(lo.ppt_to_pptx)
    assert list(sig_doc.parameters) == list(sig_ppt.parameters), (
        f"ppt_to_pptx params {list(sig_ppt.parameters)!r} must match "
        f"doc_to_docx params {list(sig_doc.parameters)!r}"
    )
    assert sig_doc.return_annotation == sig_ppt.return_annotation

    input_path = tmp_path / "in.ppt"
    input_path.write_bytes(b"fake-ppt-bytes")
    output_path = tmp_path / "out.pptx"

    with (
        patch("shutil.which", return_value=None),
        patch("os.path.isfile", return_value=False),
    ):
        with pytest.raises(RuntimeError, match="LibreOffice is not available"):
            lo.ppt_to_pptx(str(input_path), str(output_path))


# ---------------------------------------------------------------------------
# Process-group timeout kill (fix: orphaned soffice.bin ran 10+ hours after
# subprocess.run(timeout=...) only killed the direct child, not soffice.bin)
# ---------------------------------------------------------------------------

def test_timeout_kills_whole_process_group_not_just_direct_child(tmp_path):
    """On TimeoutExpired, the whole process group must be killed via os.killpg
    (start_new_session=True made proc.pid the group leader), and the call must
    surface as a RuntimeError rather than letting soffice.bin run forever."""
    input_path = tmp_path / "in.doc"
    input_path.write_bytes(b"fake-doc-bytes")
    output_path = tmp_path / "out.docx"

    fake_proc = MagicMock()
    fake_proc.pid = 12345
    fake_proc.communicate.side_effect = [
        subprocess.TimeoutExpired(cmd="soffice", timeout=120),
        ("", ""),  # second communicate() call reaps the killed process
    ]

    with (
        patch(
            "shutil.which",
            side_effect=lambda name: "/usr/bin/soffice" if name == "soffice" else None,
        ),
        patch("subprocess.Popen", return_value=fake_proc),
        patch("os.getpgid", return_value=12345) as mock_getpgid,
        patch("os.killpg") as mock_killpg,
    ):
        with pytest.raises(RuntimeError, match="timed out"):
            lo.doc_to_docx(str(input_path), str(output_path))

    mock_getpgid.assert_called_once_with(12345)
    mock_killpg.assert_called_once_with(12345, lo.signal.SIGKILL)
    assert fake_proc.communicate.call_count == 2, (
        "communicate() must be called again after killpg to reap the process"
    )


def test_timeout_falls_back_to_proc_kill_when_no_killpg(tmp_path, monkeypatch):
    """On a platform without os.killpg (e.g. Windows), fall back to proc.kill()
    instead of raising AttributeError."""
    input_path = tmp_path / "in.doc"
    input_path.write_bytes(b"fake-doc-bytes")
    output_path = tmp_path / "out.docx"

    fake_proc = MagicMock()
    fake_proc.pid = 12345
    fake_proc.communicate.side_effect = [
        subprocess.TimeoutExpired(cmd="soffice", timeout=120),
        ("", ""),
    ]

    monkeypatch.delattr(lo.os, "killpg", raising=False)

    with (
        patch(
            "shutil.which",
            side_effect=lambda name: "/usr/bin/soffice" if name == "soffice" else None,
        ),
        patch("subprocess.Popen", return_value=fake_proc),
    ):
        with pytest.raises(RuntimeError, match="timed out"):
            lo.doc_to_docx(str(input_path), str(output_path))

    fake_proc.kill.assert_called_once()


# ---------------------------------------------------------------------------
# AC-2: SUPPORTED_EXTENSIONS
# ---------------------------------------------------------------------------

def test_supported_extensions_includes_ppt():
    """AC-2: .ppt is registered as an accepted upload extension (config.py:245)."""
    from app.backend.config import SUPPORTED_EXTENSIONS

    assert ".ppt" in SUPPORTED_EXTENSIONS
