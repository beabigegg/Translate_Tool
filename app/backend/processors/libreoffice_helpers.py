"""LibreOffice headless conversion helpers for legacy .doc/.xls files."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from app.backend.config import LIBREOFFICE_PATH, LIBREOFFICE_TIMEOUT
from app.backend.utils.logging_utils import logger

# ---------------------------------------------------------------------------
# LibreOffice binary detection
# ---------------------------------------------------------------------------

_LIBREOFFICE_BINARY: Optional[str] = None
_DETECTION_DONE = False


def _find_libreoffice_binary() -> Optional[str]:
    """Detect LibreOffice binary using multiple strategies.

    Search order:
    1. LIBREOFFICE_PATH environment variable / config
    2. PATH lookup (soffice, libreoffice)
    3. Common installation paths per platform
    """
    # 1. Explicit config / env var
    if LIBREOFFICE_PATH:
        if os.path.isfile(LIBREOFFICE_PATH) and os.access(LIBREOFFICE_PATH, os.X_OK):
            return LIBREOFFICE_PATH
        logger.warning("LIBREOFFICE_PATH=%s is not executable", LIBREOFFICE_PATH)

    # 2. PATH lookup
    for name in ("soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            return found

    # 3. Common installation paths
    system = platform.system()
    candidates: list[str] = []
    if system == "Darwin":
        candidates = [
            "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        ]
    elif system == "Windows":
        for pf in (os.environ.get("ProgramFiles", ""), os.environ.get("ProgramFiles(x86)", "")):
            if pf:
                candidates.append(os.path.join(pf, "LibreOffice", "program", "soffice.exe"))
    # Linux / WSL — usually in PATH, but check common locations
    else:
        candidates = [
            "/usr/bin/soffice",
            "/usr/bin/libreoffice",
            "/usr/local/bin/soffice",
            "/snap/bin/libreoffice",
        ]

    for path in candidates:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path

    return None


def is_libreoffice_available() -> bool:
    """Return True if a usable LibreOffice binary was found (cached)."""
    global _LIBREOFFICE_BINARY, _DETECTION_DONE  # noqa: PLW0603
    if not _DETECTION_DONE:
        _LIBREOFFICE_BINARY = _find_libreoffice_binary()
        _DETECTION_DONE = True
        if _LIBREOFFICE_BINARY:
            logger.info("LibreOffice found: %s", _LIBREOFFICE_BINARY)
        else:
            logger.info("LibreOffice not found")
    return _LIBREOFFICE_BINARY is not None


def _get_binary() -> str:
    """Return cached binary path or raise."""
    if not is_libreoffice_available():
        raise RuntimeError("LibreOffice is not available")
    assert _LIBREOFFICE_BINARY is not None
    return _LIBREOFFICE_BINARY


# ---------------------------------------------------------------------------
# Core conversion via subprocess
# ---------------------------------------------------------------------------


def _libreoffice_convert(
    input_path: str,
    target_format: str,
    output_dir: str,
    timeout: int = LIBREOFFICE_TIMEOUT,
) -> str:
    """Run LibreOffice headless conversion.

    Uses a unique UserInstallation profile per call to avoid lock conflicts
    when multiple conversions run in parallel.

    Returns the path to the converted file.
    """
    binary = _get_binary()
    input_path = os.path.abspath(input_path)
    output_dir = os.path.abspath(output_dir)

    # Create a unique profile directory for parallel safety
    profile_dir = tempfile.mkdtemp(prefix="lo_profile_")
    try:
        cmd = [
            binary,
            "--headless",
            "--norestore",
            f"-env:UserInstallation=file://{profile_dir}",
            "--convert-to", target_format,
            "--outdir", output_dir,
            input_path,
        ]
        logger.debug("LibreOffice command: %s", " ".join(cmd))

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"LibreOffice conversion failed (rc={result.returncode}): "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )

        # Determine the output filename
        stem = Path(input_path).stem
        converted = os.path.join(output_dir, f"{stem}.{target_format}")
        if not os.path.isfile(converted):
            raise RuntimeError(
                f"LibreOffice conversion produced no output file: {converted}"
            )
        return converted
    finally:
        shutil.rmtree(profile_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def doc_to_docx(input_path: str, output_path: str) -> None:
    """Convert .doc to .docx via LibreOffice headless.

    Args:
        input_path: Path to input .doc file.
        output_path: Desired path for the output .docx file.
    """
    tmp_dir = tempfile.mkdtemp(prefix="lo_doc_")
    try:
        converted = _libreoffice_convert(input_path, "docx", tmp_dir)
        shutil.move(converted, output_path)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def xls_to_xlsx(input_path: str, output_path: str) -> None:
    """Convert .xls to .xlsx via LibreOffice headless.

    Args:
        input_path: Path to input .xls file.
        output_path: Desired path for the output .xlsx file.
    """
    tmp_dir = tempfile.mkdtemp(prefix="lo_xls_")
    try:
        converted = _libreoffice_convert(input_path, "xlsx", tmp_dir)
        shutil.move(converted, output_path)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
