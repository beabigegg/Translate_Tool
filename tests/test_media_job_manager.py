"""Tests for the media (audio/video) STT + translation job lifecycle
(MediaJobManager, mirrors JobManager's thread-dispatched pipeline).

Mock seam: every lazy-heavy-dependency call site is patched at the function
boundary as it is bound inside app.backend.services.media_job_manager's own
namespace (module-level `import X` -> patch `media_job_manager.X.fn`;
`from Y import fn` -> patch `media_job_manager.fn` directly) — mirrors
tests/test_quality_evaluation.py's app.backend.services.quality_evaluator.load_model
convention and tests/test_job_manager_current_segment.py's harness pattern.
None of qwen_asr/faster_whisper/silero_vad/df/soundfile/ffmpeg need to be
installed since none of stt_engine/vad_segmenter/media_preprocess's real
bodies ever execute in these tests.

Anti-tautology: assert on mock call_count/call_args (wiring actually
happened) and on the JobRecord fields a real caller would read, not just
that the background thread returned without raising.
"""

from __future__ import annotations

import threading
import time
from unittest.mock import ANY, MagicMock, patch

from app.backend.models.media_transcript import TranscriptSegment


def _wait_for_terminal(job, timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if job.status in ("completed", "failed", "cancelled"):
            return
        time.sleep(0.02)
    raise TimeoutError(f"job did not reach a terminal state in {timeout}s; status={job.status}")


def _make_segment(text: str = "hello", language: str = "en") -> TranscriptSegment:
    return TranscriptSegment(start=0.0, end=1.0, text=text, language=language)


def _make_fake_client() -> MagicMock:
    client = MagicMock()
    client.model = "test-model"
    client.unload.return_value = (True, "ok")
    return client


# ---------------------------------------------------------------------------
# Happy path: full stage sequence, ends completed with output_txt_path set
# ---------------------------------------------------------------------------

def test_happy_path_runs_expected_stage_sequence_and_completes(tmp_path):
    from app.backend.services.media_job_manager import MediaJobManager

    media_file = tmp_path / "input.mp4"
    media_file.write_bytes(b"fake media bytes")
    extracted_wav = tmp_path / "extracted.wav"
    extracted_wav.write_bytes(b"RIFF-fake-wav")
    denoised_wav = tmp_path / "denoised.wav"
    denoised_wav.write_bytes(b"RIFF-fake-wav-denoised")

    fake_client = _make_fake_client()

    def fake_translate_transcript(transcript, targets, client, stop_flag=None, log=None, status_callback=None):
        for seg in transcript.segments:
            for t in targets:
                seg.translated_text[t] = f"[{t}] {seg.text}"

    with patch("app.backend.services.media_job_manager.media_preprocess.extract_audio",
               return_value=extracted_wav) as mock_extract, \
         patch("app.backend.services.media_job_manager.media_preprocess.denoise_audio",
               return_value=denoised_wav) as mock_denoise, \
         patch("app.backend.services.media_job_manager.vad_segmenter.segment_by_voice_activity",
               return_value=[(0.0, 1.0)]) as mock_vad, \
         patch("app.backend.services.media_job_manager.stt_engine.transcribe",
               return_value=[_make_segment()]) as mock_transcribe, \
         patch("app.backend.services.media_job_manager.resolve_media_client",
               return_value=(fake_client, "test-model")) as mock_resolve, \
         patch("app.backend.services.media_job_manager.media_translation.translate_transcript",
               side_effect=fake_translate_transcript) as mock_translate:

        jm = MediaJobManager()
        job = jm.create_job(media_file, targets=["en"])
        _wait_for_terminal(job)

    assert job.status == "completed"
    assert job.stage == "completed"
    assert job.error is None
    assert job.output_txt_path is not None
    assert job.output_txt_path.exists()
    content = job.output_txt_path.read_text(encoding="utf-8")
    assert "[en] hello" in content

    # Wiring: each stage function called exactly once, with the expected
    # data threaded from the previous stage's output. VAD runs on the
    # EXTRACTED (not yet denoised) audio — denoise now runs after VAD so it
    # can chunk by VAD's speech-span boundaries instead of a fixed time
    # window (see media_preprocess.denoise_audio's docstring) — and denoise
    # receives the VAD segments as its third argument.
    mock_extract.assert_called_once_with(job.media_path, ANY)
    mock_vad.assert_called_once_with(str(extracted_wav))
    mock_denoise.assert_called_once_with(extracted_wav, ANY, [(0.0, 1.0)])
    # The intermediate-wav output_dir passed to both calls must be a
    # subdirectory of the job's own dir (cleaned up by _remove_job), never a
    # bare tempfile.mkdtemp() the pipeline never tracks/cleans.
    extract_out_dir = mock_extract.call_args.args[1]
    assert extract_out_dir == mock_denoise.call_args.args[1]
    assert job.media_path.parent.parent in extract_out_dir.parents
    mock_transcribe.assert_called_once_with(str(denoised_wav), [(0.0, 1.0)])

    resolve_call = mock_resolve.call_args
    assert resolve_call.args == (None, None, None, None, ["en"])

    translate_call = mock_translate.call_args
    assert translate_call.args[0] is job.transcript
    assert translate_call.args[1] == ["en"]
    assert translate_call.args[2] is fake_client
    assert translate_call.kwargs["stop_flag"] is job.stop_flag

    # Selection, not just count: the transcript actually produced must be the
    # one carried into translate_transcript and written to disk.
    assert job.transcript is not None
    assert job.transcript.segments[0].text == "hello"

    # Stage sequence, in order, as recorded through the real _log() calls.
    # VAD before denoise: see media_preprocess.denoise_audio's docstring.
    stage_names = [line.split("[STAGE] ", 1)[1] for line in job.logs if "[STAGE]" in line]
    assert stage_names == [
        "extracting", "vad_segmenting", "denoising", "transcribing", "translating", "rendering",
    ]


# ---------------------------------------------------------------------------
# A stage-raising exception sets status=failed with job.error populated
# ---------------------------------------------------------------------------

def test_stage_exception_sets_failed_status_with_error(tmp_path):
    from app.backend.services.media_job_manager import MediaJobManager

    media_file = tmp_path / "input.mp4"
    media_file.write_bytes(b"fake media bytes")
    extracted_wav = tmp_path / "extracted.wav"
    extracted_wav.write_bytes(b"RIFF-fake-wav")

    with patch("app.backend.services.media_job_manager.media_preprocess.extract_audio",
               return_value=extracted_wav), \
         patch("app.backend.services.media_job_manager.media_preprocess.denoise_audio",
               return_value=extracted_wav), \
         patch("app.backend.services.media_job_manager.vad_segmenter.segment_by_voice_activity",
               return_value=[(0.0, 1.0)]), \
         patch("app.backend.services.media_job_manager.stt_engine.transcribe",
               side_effect=RuntimeError("boom")) as mock_transcribe, \
         patch("app.backend.services.media_job_manager.resolve_media_client") as mock_resolve, \
         patch("app.backend.services.media_job_manager.media_translation.translate_transcript") as mock_translate:

        jm = MediaJobManager()
        job = jm.create_job(media_file, targets=["en"])
        _wait_for_terminal(job)

    assert job.status == "failed"
    assert job.stage == "failed"
    assert job.error == "boom"

    mock_transcribe.assert_called_once()
    # Pipeline must stop at the failing stage — later stages never reached.
    mock_resolve.assert_not_called()
    mock_translate.assert_not_called()
    assert any("[ERROR] boom" in line for line in job.logs)


# ---------------------------------------------------------------------------
# cancel_job before pipeline completion results in status=cancelled
# ---------------------------------------------------------------------------

def test_cancel_before_completion_sets_cancelled_status(tmp_path):
    from app.backend.services.media_job_manager import MediaJobManager

    media_file = tmp_path / "input.mp4"
    media_file.write_bytes(b"fake media bytes")
    extracted_wav = tmp_path / "extracted.wav"
    extracted_wav.write_bytes(b"RIFF-fake-wav")

    reached_vad = threading.Event()
    release_vad = threading.Event()

    def blocking_vad(wav_path):
        reached_vad.set()
        if not release_vad.wait(timeout=10.0):
            raise TimeoutError("test never released the blocked vad stage")
        return [(0.0, 1.0)]

    with patch("app.backend.services.media_job_manager.media_preprocess.extract_audio",
               return_value=extracted_wav), \
         patch("app.backend.services.media_job_manager.media_preprocess.denoise_audio",
               return_value=extracted_wav) as mock_denoise, \
         patch("app.backend.services.media_job_manager.vad_segmenter.segment_by_voice_activity",
               side_effect=blocking_vad), \
         patch("app.backend.services.media_job_manager.stt_engine.transcribe") as mock_transcribe, \
         patch("app.backend.services.media_job_manager.resolve_media_client") as mock_resolve, \
         patch("app.backend.services.media_job_manager.media_translation.translate_transcript") as mock_translate:

        jm = MediaJobManager()
        job = jm.create_job(media_file, targets=["en"])

        # Synchronize with the background thread via the event instead of a
        # bare sleep-based race: wait until the pipeline is actually blocked
        # inside the vad_segmenting stage before requesting cancellation.
        assert reached_vad.wait(timeout=10.0), "pipeline never reached vad_segmenting stage"
        assert jm.cancel_job(job.job_id) is True
        release_vad.set()

        _wait_for_terminal(job)

    assert job.status == "cancelled"
    assert job.stage == "cancelled"

    # _check_stop() must fire before the next stage — denoising/transcribing/
    # translating never run once stop_flag was set. VAD now runs BEFORE
    # denoise (see media_preprocess.denoise_audio's docstring), so this also
    # guards that cancelling mid-VAD doesn't let a later denoise slip through.
    mock_denoise.assert_not_called()
    mock_transcribe.assert_not_called()
    mock_resolve.assert_not_called()
    mock_translate.assert_not_called()

    assert any("Stop requested" in line for line in job.logs)
    assert any("Media job cancelled" in line for line in job.logs)


# ---------------------------------------------------------------------------
# Model memory release: VAD/STT model caches are dropped as soon as their
# own stage exits, not held for the rest of the pipeline's lifetime.
# ---------------------------------------------------------------------------

def test_vad_and_stt_models_unloaded_immediately_after_their_stage(tmp_path):
    from app.backend.services.media_job_manager import MediaJobManager

    media_file = tmp_path / "input.mp4"
    media_file.write_bytes(b"fake media bytes")
    extracted_wav = tmp_path / "extracted.wav"
    extracted_wav.write_bytes(b"RIFF-fake-wav")

    fake_client = _make_fake_client()
    call_order = []

    def fake_vad(wav_path):
        call_order.append("vad")
        return [(0.0, 1.0)]

    def fake_denoise(wav_path, out_dir, vad_segments):
        call_order.append("denoise")
        return wav_path

    def fake_transcribe(wav_path, vad_segments):
        call_order.append("transcribe")
        return [_make_segment()]

    def fake_resolve(*args, **kwargs):
        call_order.append("resolve_client")
        return fake_client, "test-model"

    with patch("app.backend.services.media_job_manager.media_preprocess.extract_audio",
               return_value=extracted_wav), \
         patch("app.backend.services.media_job_manager.media_preprocess.denoise_audio",
               side_effect=fake_denoise), \
         patch("app.backend.services.media_job_manager.vad_segmenter.segment_by_voice_activity",
               side_effect=fake_vad), \
         patch("app.backend.services.media_job_manager.vad_segmenter.unload_model",
               side_effect=lambda: call_order.append("vad_unload")) as mock_vad_unload, \
         patch("app.backend.services.media_job_manager.stt_engine.transcribe",
               side_effect=fake_transcribe), \
         patch("app.backend.services.media_job_manager.stt_engine.unload_model",
               side_effect=lambda: call_order.append("stt_unload")) as mock_stt_unload, \
         patch("app.backend.services.media_job_manager.resolve_media_client",
               side_effect=fake_resolve), \
         patch("app.backend.services.media_job_manager.media_translation.translate_transcript"):

        jm = MediaJobManager()
        job = jm.create_job(media_file, targets=["en"])
        _wait_for_terminal(job)

    assert job.status == "completed"
    mock_vad_unload.assert_called_once()
    mock_stt_unload.assert_called_once()
    # vad_segmenter.unload_model() must run right after VAD produces segments
    # (before denoise/transcribe even start — the model is never needed again),
    # and stt_engine.unload_model() must run right after transcribe (before
    # the translating stage's resolve_media_client call).
    assert call_order == [
        "vad", "vad_unload", "denoise", "transcribe", "stt_unload", "resolve_client",
    ]


def test_cancel_job_returns_false_for_unknown_job_id():
    from app.backend.services.media_job_manager import MediaJobManager

    jm = MediaJobManager()
    assert jm.cancel_job("does-not-exist") is False
