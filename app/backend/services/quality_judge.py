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

        for iteration in range(max_iterations):
            attempts += 1

            # Join current translations for display scoring
            joined_source = "\n\n".join(src for _, src, _ in blocks)
            joined_translation = "\n\n".join(current_translations[bid] for bid, _, _ in blocks)

            result = self.evaluate(joined_source, joined_translation, feedback=current_feedback)

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
