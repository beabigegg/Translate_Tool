"""LLM-as-judge quality evaluation service (p3-llm-judge).

Design decisions:
  D4: Judge instantiates its own OllamaClient(model=JUDGE_MODEL) — never model_router.
  D5: Any exception in the judge pass is caught, logged at WARNING, and returns
      JudgeResult(judge_status="unavailable"). The job always completes normally.
  D6: Score extraction: JSON parse first; on failure scan for first of 高/中/低
      (exact token, synonyms not inferred); default to unavailable if none found.
  D7: re-translation stores per-block map {block_id: text} for the apply path.

Mock seam: app.backend.services.quality_judge.QualityJudge
"""

from __future__ import annotations

import json
import logging
from typing import Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Score tokens ordered by extraction priority (highest priority first)
_SCORE_TOKENS = ("高", "中", "低")

# Prompt template: elicit JSON with score and feedback
_JUDGE_PROMPT_TEMPLATE = """\
You are a translation quality evaluator. Given the source text and its translation, \
rate the translation quality.

Source text:
{source}

Translation:
{translation}

{feedback_section}
Respond ONLY with a JSON object in this exact format:
{{"score": "高|中|低", "feedback": "your feedback here"}}

Where:
- 高 = high quality, accurate and natural translation
- 中 = acceptable quality, some issues but understandable
- 低 = poor quality, significant errors or unnatural translation

Your response (JSON only):"""

_FEEDBACK_SECTION_TEMPLATE = """\
Previous feedback from quality reviewer:
{feedback}

Please re-evaluate the revised translation with the above context in mind.

"""


class QualityJudge:
    """LLM-as-judge quality evaluator using a dedicated local Ollama model (D4).

    The judge is intentionally isolated from model_router (D4): it always uses
    the configured JUDGE_MODEL directly via OllamaClient.
    """

    def __init__(self) -> None:
        from app.backend.clients.ollama_client import OllamaClient
        from app.backend.config import JUDGE_MODEL, OLLAMA_BASE_URL

        self.model = JUDGE_MODEL
        self._client = OllamaClient(base_url=OLLAMA_BASE_URL, model=JUDGE_MODEL)

    def _parse_score(self, response_text: str) -> Optional[str]:
        """Extract score from judge response (D6).

        Strategy:
        1. Try JSON parse and extract 'score' field.
        2. On parse failure, scan raw text for first of 高/中/低 (exact token).
        3. Return None if neither yields a valid token.
        """
        # Step 1: JSON parse
        try:
            # Extract JSON block if there is surrounding text
            text = response_text.strip()
            # Find first '{' and last '}'
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                json_str = text[start : end + 1]
                parsed = json.loads(json_str)
                score = parsed.get("score", "").strip()
                if score in _SCORE_TOKENS:
                    return score
        except (json.JSONDecodeError, ValueError, AttributeError):
            pass

        # Step 2: Scan raw text for first exact token
        for token in _SCORE_TOKENS:
            if token in response_text:
                return token

        # Step 3: No valid token found
        return None

    def _parse_feedback(self, response_text: str) -> str:
        """Extract feedback string from judge response."""
        try:
            text = response_text.strip()
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                json_str = text[start : end + 1]
                parsed = json.loads(json_str)
                return str(parsed.get("feedback", "")).strip()
        except (json.JSONDecodeError, ValueError, AttributeError):
            pass
        return ""

    def judge_block(self, src: str, tgt: str) -> float:
        """Score a single translation block (AC-5 — per-block judge scoring).

        Reuses :meth:`evaluate` to score one (source, translation) pair and
        converts the categorical 高/中/低 result to a float in [0.0, 1.0].

        Args:
            src: Source text for this block.
            tgt: Translated text for this block.

        Returns:
            Float score: 1.0 for 高, 0.5 for 中, 0.0 for 低 or unavailable.
        """
        result = self.evaluate(src, tgt)
        _score_map = {"高": 1.0, "中": 0.5, "低": 0.0}
        return _score_map.get(result.get("score"), 0.0)  # type: ignore[return-value]

    def judge_layout(self, page_image: "PIL.Image.Image") -> int:  # noqa: F821
        """Score PDF page layout quality via Gemma (AC-6 — MLLM layout scoring).

        Takes an in-memory PIL Image of a rendered page and returns an integer
        quality score 1–5 (1 = very poor, 5 = excellent).  Only the local Gemma
        socket is used (BR-32 / ADR 0007) — this method MUST NOT route to any
        cloud provider.

        Args:
            page_image: PIL.Image.Image of the rendered output page.
                        MUST be an in-memory image object, never a file path.

        Returns:
            Integer score in [1, 5].  Returns 0 on any failure (safe-degrade).
        """
        import base64
        import io

        try:
            buf = io.BytesIO()
            page_image.save(buf, format="PNG")
            _img_b64 = base64.b64encode(buf.getvalue()).decode()

            prompt = (
                "Rate the layout quality of this translated document page on a scale of 1 to 5.\n"
                "1 = very poor (severe overlap, cut-off text, unreadable);\n"
                "2 = poor (notable spacing or alignment issues);\n"
                "3 = acceptable (minor issues, mostly readable);\n"
                "4 = good (clean layout, well aligned);\n"
                "5 = excellent (perfect layout, professional quality).\n"
                "Respond with ONLY the single digit (1, 2, 3, 4, or 5)."
            )
            payload = self._client._build_no_system_payload(prompt)
            ok, response = self._client._call_ollama(payload)
            if not ok:
                logger.warning("[Judge] judge_layout(): Gemma call failed")
                return 0
            for char in response.strip():
                if char.isdigit() and int(char) in range(1, 6):
                    return int(char)
            logger.warning(
                "[Judge] judge_layout(): could not parse score from response: %r",
                response[:100],
            )
            return 0
        except Exception as exc:
            logger.warning("[Judge] judge_layout() exception: %s: %s", type(exc).__name__, exc)
            return 0

    def evaluate(self, source_text: str, translated_text: str, feedback: str = "") -> dict:
        """Score a (source, translation) pair.

        Args:
            source_text: Original source text.
            translated_text: Candidate translation.
            feedback: Optional prior feedback for re-evaluation context.

        Returns:
            Dict with keys: judge_status, score, feedback.
        """
        try:
            feedback_section = ""
            if feedback:
                feedback_section = _FEEDBACK_SECTION_TEMPLATE.format(feedback=feedback)

            prompt = _JUDGE_PROMPT_TEMPLATE.format(
                source=source_text,
                translation=translated_text,
                feedback_section=feedback_section,
            )
            payload = self._client._build_no_system_payload(prompt)
            ok, response = self._client._call_ollama(payload)
            if not ok:
                raise RuntimeError(f"Ollama judge call failed: {response}")
            score = self._parse_score(response)
            extracted_feedback = self._parse_feedback(response)

            if score is None:
                logger.warning(
                    "[Judge] Score parse failure — response did not contain 高/中/低: %r",
                    response[:200],
                )
                return {"judge_status": "unavailable", "score": None, "feedback": ""}

            return {
                "judge_status": "available",
                "score": score,
                "feedback": extracted_feedback,
            }
        except Exception as exc:
            logger.warning("[Judge] evaluate() exception: %s: %s", type(exc).__name__, exc)
            return {"judge_status": "unavailable", "score": None, "feedback": ""}

    def run_judge_loop(
        self,
        job_id: str,
        blocks: List[Tuple[str, str, str]],
        translate_fn: Callable[[str, str], str],
    ) -> "JudgeResult":
        """Run the judge re-translation loop over collected block pairs.

        Args:
            job_id: Job identifier (for logging).
            blocks: List of (block_id, source_text, translated_text) tuples.
            translate_fn: Callable(source_text, feedback) -> re-translated_text.

        Returns:
            JudgeResult instance (never raises — D5/BR-74).
        """
        # Lazy import to avoid circular import at module level
        from app.backend.services.job_manager import JudgeResult
        from app.backend.config import JUDGE_MAX_ITERATIONS

        try:
            return self._run_judge_loop_impl(job_id, blocks, translate_fn, JUDGE_MAX_ITERATIONS)
        except Exception as exc:
            logger.warning(
                "judge failed for job_id=%s: %s: %s",
                job_id,
                type(exc).__name__,
                exc,
            )
            return JudgeResult(
                job_id=job_id,
                judge_status="unavailable",
                score=None,
                source_text=None,
                translated_text=None,
                feedback=None,
                attempts=0,
                model=None,
                retranslated_blocks=None,
            )

    def _run_judge_loop_impl(
        self,
        job_id: str,
        blocks: List[Tuple[str, str, str]],
        translate_fn: Callable[[str, str], str],
        max_iterations: int,
    ) -> "JudgeResult":
        """Implementation of the judge loop (called within exception boundary)."""
        from app.backend.services.job_manager import JudgeResult

        if not blocks:
            return JudgeResult(
                job_id=job_id,
                judge_status="unavailable",
                score=None,
                source_text=None,
                translated_text=None,
                feedback=None,
                attempts=0,
                model=self.model,
                retranslated_blocks=None,
            )

        # Build joined source/translated for display
        all_sources = [src for _, src, _ in blocks]
        # Current translations start as the original MT outputs
        current_translations: Dict[str, str] = {bid: mt for bid, _, mt in blocks}
        current_feedback = ""
        final_score: Optional[str] = None
        final_feedback = ""
        attempts = 0
        retranslated_blocks: Optional[Dict[str, str]] = None

        # Score-priority map for aggregating per-block scores (lower index = worse quality).
        _score_priority: dict = {"低": 0, "中": 1, "高": 2}

        for iteration in range(max_iterations):
            attempts += 1

            # Score each block individually (IP-6 — per-block, not whole-doc join).
            per_block_results = [
                (bid, self.evaluate(src, current_translations[bid], feedback=current_feedback))
                for bid, src, _ in blocks
            ]

            # Degrade to unavailable if ANY block evaluation failed.
            if any(r.get("judge_status") != "available" for _, r in per_block_results):
                return JudgeResult(
                    job_id=job_id,
                    judge_status="unavailable",
                    score=None,
                    source_text=None,
                    translated_text=None,
                    feedback=None,
                    attempts=attempts,
                    model=self.model,
                    retranslated_blocks=None,
                )

            # Aggregate: use the worst per-block score to drive loop control.
            valid_scores = [
                r.get("score") for _, r in per_block_results if r.get("score") in _score_priority
            ]
            aggregate_score: Optional[str] = (
                min(valid_scores, key=lambda s: _score_priority[s]) if valid_scores else None
            )

            # Combine per-block feedback for the re-translation pass.
            combined_feedback = "; ".join(
                r.get("feedback", "")
                for _, r in per_block_results
                if r.get("feedback")
            )

            # Build a synthetic result dict for the existing post-loop logic.
            result = {
                "judge_status": "available",
                "score": aggregate_score,
                "feedback": combined_feedback,
            }

            if result["judge_status"] != "available":
                # Judge call failed — degrade to unavailable
                return JudgeResult(
                    job_id=job_id,
                    judge_status="unavailable",
                    score=None,
                    source_text=None,
                    translated_text=None,
                    feedback=None,
                    attempts=attempts,
                    model=self.model,
                    retranslated_blocks=None,
                )

            final_score = result["score"]
            final_feedback = result["feedback"]
            current_feedback = final_feedback

            # Score 高 → stop immediately (BR-72)
            if final_score == "高":
                break

            # Score 中 or 低 → re-translate with feedback (BR-75), unless last iteration
            if iteration < max_iterations - 1:
                new_translations: Dict[str, str] = {}
                for bid, src, _ in blocks:
                    try:
                        new_mt = translate_fn(src, current_feedback)
                        new_translations[bid] = new_mt
                    except Exception as tr_exc:
                        logger.warning(
                            "[Judge] re-translate failed for block %s job_id=%s: %s",
                            bid,
                            job_id,
                            tr_exc,
                        )
                        # Keep previous translation on per-block failure
                        new_translations[bid] = current_translations[bid]
                current_translations = new_translations
                retranslated_blocks = dict(current_translations)
            else:
                # Last iteration — still record what we have as retranslated
                if final_score in ("中", "低"):
                    retranslated_blocks = dict(current_translations)

        # If score was 高 on first attempt, no re-translation needed (retranslated_blocks stays None)
        # If we went through iterations and improved, retranslated_blocks holds the final map

        # Build display text
        joined_source = "\n\n".join(src for _, src, _ in blocks)
        final_joined_translation = "\n\n".join(current_translations[bid] for bid, _, _ in blocks)

        return JudgeResult(
            job_id=job_id,
            judge_status="available",
            score=final_score,
            source_text=joined_source,
            translated_text=final_joined_translation,
            feedback=final_feedback,
            attempts=attempts,
            model=self.model,
            retranslated_blocks=retranslated_blocks,
        )
