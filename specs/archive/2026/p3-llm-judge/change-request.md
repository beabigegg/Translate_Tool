# Change Request

## Original Request

Add Gemma-based LLM-as-judge quality review service. After each translation, Gemma evaluates the result and assigns a 3-tier score (低/中/高). If score is 中 or 低, judge feedback is sent back to the translation model for re-translation, up to 3 attempts. Judge results (score, source text, translated text, feedback) are exposed via a new API endpoint and displayed in the frontend job detail UI. Applies to all document formats (DOCX/PPTX/XLSX/PDF).

User clarifications:
- Judge model: Gemma (via Ollama)
- Translation model: current configured OSS model (whatever is set in settings)
- Max re-translation attempts: 3
- Score tiers: 低 / 中 / 高
- Re-translate trigger: 中 or 低
- UI: Judge results (score + source text + translated text + judge feedback) shown in job detail
- Scope: all document formats (DOCX/PPTX/XLSX/PDF)
- Multimodal layout regression detection: deferred to future change
- Re-translation reflection: when judge produces a re-translated result, the UI shows a confirmation dialog asking the user whether to overwrite the download file. If confirmed, the system re-renders the document with the re-translated text and overwrites the job's output file. Overwrite is destructive (no backup of original).

## Business / User Goal

Strengthen translation quality to compete with commercial translation tools by adding an automated review-and-refine loop. Targets 術語專業度 (terminology accuracy) and 翻譯流暢度 (translation fluency) as primary quality dimensions.

## Non-goals

- Multimodal layout regression detection (deferred)
- DeepL or other commercial MT integration
- Per-cell judge for table elements
- Keeping a backup of the original file after apply (overwrite is destructive)

## Constraints

- Gemma judge runs via Ollama (local); must not require DeepSeek API for judging
- Max 3 re-translation iterations to avoid runaway cost/latency
- Judge is optional (can be disabled via feature flag); if Gemma unavailable, translation completes without judge pass
- No new external dependencies beyond what is already in requirements.txt

## Known Context

- Existing: COMET/xCOMET neural QE (numeric score, GET /api/jobs/{id}/quality)
- Existing: CRITIQUE_LOOP_ENABLED flag (partially implemented critique loop)
- Existing: model_router with multi-provider fallback chain
- Existing: post_translate_hook in orchestrator wired to 5 processors
- Judge is separate from COMET QE; both can coexist

## Open Questions

- None — all design decisions confirmed by user
