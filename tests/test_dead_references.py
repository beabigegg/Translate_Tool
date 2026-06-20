"""Dead-reference grep tests (AC-5, AC-6).

Each test invokes grep in a subprocess against app/ and tests/ (excluding this
file itself and the openai_compatible_client test file that references removed
methods explicitly in its own test corpus).  Asserts returncode != 0 (zero
hits in production code).

Symbols checked: every identifier removed in change remove-cross-model-refinement.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
_APP_DIR = str(_REPO_ROOT / "app")
_TESTS_DIR = str(_REPO_ROOT / "tests")

# Files excluded from dead-reference grep: this file itself (its own function
# bodies mention the removed symbol names in docstrings / assertion messages).
_EXCLUDE_FILES = [
    str(Path(__file__)),  # self-reference
]


def _grep(pattern: str) -> subprocess.CompletedProcess:
    """Run grep against app/ and tests/, excluding self-referencing test files."""
    cmd = ["grep", "-rn", "--include=*.py"]
    for excl in _EXCLUDE_FILES:
        cmd += ["--exclude", Path(excl).name]
    cmd += [pattern, _APP_DIR, _TESTS_DIR]
    return subprocess.run(cmd, capture_output=True, text=True)


def test_no_refine_translation_in_app():
    """refine_translation must not appear anywhere in app/ or tests/."""
    result = _grep("refine_translation")
    assert result.returncode != 0, (
        f"Found 'refine_translation' — dead code not fully removed:\n{result.stdout}"
    )


def test_no_refine_client_in_app():
    """refine_client must not appear anywhere in app/ or tests/."""
    result = _grep("refine_client")
    assert result.returncode != 0, (
        f"Found 'refine_client' — dead code not fully removed:\n{result.stdout}"
    )


def test_no_refine_model_in_app():
    """refine_model must not appear anywhere in app/ or tests/."""
    result = _grep("refine_model")
    assert result.returncode != 0, (
        f"Found 'refine_model' — dead code not fully removed:\n{result.stdout}"
    )


def test_no_cross_model_refinement_in_app():
    """CROSS_MODEL_REFINEMENT must not appear anywhere in app/ or tests/."""
    result = _grep("CROSS_MODEL_REFINEMENT")
    assert result.returncode != 0, (
        f"Found 'CROSS_MODEL_REFINEMENT' — dead code not fully removed:\n{result.stdout}"
    )


def test_no_refinement_enabled_in_app():
    """REFINEMENT_ENABLED must not appear anywhere in app/ or tests/."""
    result = _grep("REFINEMENT_ENABLED")
    assert result.returncode != 0, (
        f"Found 'REFINEMENT_ENABLED' — dead code not fully removed:\n{result.stdout}"
    )


def test_no_refinement_min_chars_in_app():
    """REFINEMENT_MIN_CHARS must not appear anywhere in app/ or tests/."""
    result = _grep("REFINEMENT_MIN_CHARS")
    assert result.returncode != 0, (
        f"Found 'REFINEMENT_MIN_CHARS' — dead code not fully removed:\n{result.stdout}"
    )


def test_no_build_refine_prompt_in_app():
    """_build_refine_prompt must not appear anywhere in app/ or tests/."""
    result = _grep("_build_refine_prompt")
    assert result.returncode != 0, (
        f"Found '_build_refine_prompt' — dead code not fully removed:\n{result.stdout}"
    )


def test_no_build_refine_system_prompt_in_app():
    """_build_refine_system_prompt must not appear anywhere in app/ or tests/."""
    result = _grep("_build_refine_system_prompt")
    assert result.returncode != 0, (
        f"Found '_build_refine_system_prompt' — dead code not fully removed:\n{result.stdout}"
    )


def test_no_refiner_num_ctx_in_app():
    """refiner_num_ctx must not appear anywhere in app/ or tests/."""
    result = _grep("refiner_num_ctx")
    assert result.returncode != 0, (
        f"Found 'refiner_num_ctx' — dead code not fully removed:\n{result.stdout}"
    )


def test_no_hy_mt_in_app():
    """HY-MT model references must not appear anywhere in app/ or tests/."""
    result = _grep("HY-MT")
    assert result.returncode != 0, (
        f"Found 'HY-MT' — dead code not fully removed:\n{result.stdout}"
    )


def test_no_translategemma_in_app():
    """TranslateGemma must not appear anywhere in app/ or tests/."""
    result = _grep("TranslateGemma")
    assert result.returncode != 0, (
        f"Found 'TranslateGemma' — dead code not fully removed:\n{result.stdout}"
    )
