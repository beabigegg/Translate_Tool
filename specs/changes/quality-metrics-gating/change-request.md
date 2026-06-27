# Change Request

## Original Request

Wave 3 Track H — implement quality metrics and critique gating (improvement-plan §階段 4):
- 4.1 CometKiwi per-segment QE enabled by default; low-score segments routed to re-translation
- 4.2 LLM-as-judge changed from whole-document single score to per-segment/per-block; for PDF pages, add MLLM-as-judge layout scoring 1-5 (reuse existing Gemma judge)
- 4.3 Critique loop adds scoring gate: only adopt revision if revised score ≥ original score
- 4.4 Long-document path (`translate_document()`) achieves parity with short-doc path: add terms, critique, and 50-token overlap context

## Business / User Goal

Current quality infrastructure has critical gaps:
- COMET QE is off by default; when on, it scores the whole document not segments, so low-quality segments are not caught.
- The LLM judge gives one "high/medium/low" for the whole file — useless for pinpointing problems.
- The critique loop adds latency (~2× LLM calls) but never checks if the revision is actually better; the last iteration always wins even if it's worse.
- The long-doc path (`translate_document()`, used for DOCX >40k chars) ignores terms and skips critique — producing lower quality than the short-doc path on large files.

## Non-goals

- Frontend quality display changes (separate future change)
- Collecting a human-annotation MQM corpus (out of scope)
- New OCR / layout detection changes (Track G, already done)
- xCOMET error-span highlighting (follow-on; 4.1 focuses on CometKiwi QE runtime)

## Constraints

- Track B (metrics harness, with rasterize infrastructure) must already be merged for 4.2 MLLM layout scoring
- Track C (fix dead context-window settings) must already be merged before 4.4 long-doc parity
- `QE_ENABLED` defaults may need env-contract update; must run `cdd-kit openapi export` after any API surface change
- `JUDGE_ENABLED` remains false by default; 4.2 changes are additive to existing judge path
- `services/translation_service.py` is a conflict zone with Track C — Track C must be merged first

## Known Context

- `quality_evaluator.py`: COMET/xCOMET, lazy-loaded, currently off by default. Per-segment QE requires calling `evaluate()` per segment and checking against a threshold.
- `quality_judge.py`: LLM judge. Currently `judge_translation()` returns one score for the whole doc (`quality_judge.py:238-241`). Per-segment means calling per block/paragraph.
- `translation_service.py`: critique loop at `_run_critique_loop()`. Currently last iteration always wins with no score comparison.
- `translate_document()` at `translation_service.py:384-533`: receives `terms` but does not use them; does not call critique; overlap is only for dedup not context.
- `config.py`: `QE_ENABLED`, `CRITIQUE_LOOP_ENABLED`, `JUDGE_ENABLED` are the feature flags to modify.

## Open Questions

None — improvement-plan §階段 4 acceptance criteria are clear.

## Requested Delivery Date / Priority

Wave 3, parallel with Track F. High priority.
