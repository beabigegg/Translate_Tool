"""Data-boundary tests for JobRecord + JudgeResult (p3-llm-judge).

Verifies the dataclass fields defined in job_manager.py match
contracts/data/data-shape-contract.md §LLM Judge Result Representation.
"""

from __future__ import annotations

from pathlib import Path
import dataclasses
from typing import get_type_hints


# ---------------------------------------------------------------------------
# AC-1 / contract: JudgeResult field presence and types
# ---------------------------------------------------------------------------

def test_judge_result_fields_match_contract():
    """JudgeResult has all contract-required fields with correct types."""
    from app.backend.services.job_manager import JudgeResult

    fields = {f.name: f for f in dataclasses.fields(JudgeResult)}

    required_fields = {
        "job_id",
        "judge_status",
        "score",
        "source_text",
        "translated_text",
        "feedback",
        "attempts",
        "model",
        "retranslated_blocks",
    }

    for name in required_fields:
        assert name in fields, f"JudgeResult missing required field: {name!r}"


def test_judge_result_optional_fields_default_none():
    """Optional JudgeResult fields default to None (contract §data-shape)."""
    from app.backend.services.job_manager import JudgeResult

    jr = JudgeResult(job_id="j", judge_status="available")

    assert jr.score is None
    assert jr.source_text is None
    assert jr.translated_text is None
    assert jr.feedback is None
    assert jr.attempts == 0, "attempts should default to 0"
    assert jr.model is None
    assert jr.retranslated_blocks is None


# ---------------------------------------------------------------------------
# AC-1 / contract: JobRecord has judge and judge_apply_status
# ---------------------------------------------------------------------------

def test_job_record_has_judge_fields():
    """JobRecord has judge (Optional[JudgeResult]) and judge_apply_status (Optional[str])."""
    from app.backend.services.job_manager import JobRecord
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        job = JobRecord(
            job_id="test-fields",
            input_dir=Path(tmp) / "input",
            output_dir=Path(tmp) / "output",
        )

        # Fields must exist
        assert hasattr(job, "judge"), "JobRecord missing 'judge' field"
        assert hasattr(job, "judge_apply_status"), "JobRecord missing 'judge_apply_status' field"

        # Both default to None
        assert job.judge is None, "job.judge must default to None"
        assert job.judge_apply_status is None, "job.judge_apply_status must default to None"
