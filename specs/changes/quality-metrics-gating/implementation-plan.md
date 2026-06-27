---
change-id: quality-metrics-gating
schema-version: 0.1.0
last-changed: 2026-06-27
---

# Implementation Plan: quality-metrics-gating

> Worktree: all implementation happens in `.claude/worktrees/quality-metrics-gating/`
> on branch `feat/quality-metrics-gating`. Run all `cdd-kit`, `pytest`, and edit
> commands from that worktree root.

## Objective

Make the translation-quality subsystem score-driven (design.md §Summary):
CometKiwi QE default-on with a per-segment rescore threshold; a non-regression
critique gate; per-block (not whole-doc) judge scoring plus an additive PDF
MLLM layout score; and `translate_document()` brought to short-doc parity by
delegating chunks to `translate_texts()`. All behaviour stays flag-reversible.

## Execution Scope

### In Scope (this change, allowed paths)
- `config.py`: `QE_ENABLED` default false→true; add `QE_RESCORE_THRESHOLD` (AC-3, AC-4).
- `quality_evaluator.py`: reuse `score_blocks` as the inline critique-gate scorer (AC-1, AC-7).
- `translation_service.py` critique loop: non-regression adoption gate + no-QE heuristic fallback (AC-7, AC-8).
- `translation_service.py` `translate_document()`: delegate chunk translation to `translate_texts()` with overlap-as-context (AC-9, AC-10, AC-11).
- `quality_judge.py`: per-block scoring loop via existing `evaluate()`; new `judge_layout(image)` MLLM method (AC-5 scoring, AC-6 method).
- Contracts: env, business-rules, data-shape (see Contract Updates).

### Out of Scope / blocked on expansion (do NOT implement until CER approved)
- **AC-2 rescore routing** — collecting below-threshold segments and re-translating
  lives in `job_manager.py` (lines ~416-442, post-translate QE hook). Not in Allowed
  Paths → CER-002.
- **AC-5 per-block persistence** — the `JudgeResult` dataclass storing per-block scores
  is defined in `job_manager.py` (lines ~43-57). The scoring loop is in scope; persisting
  the per-block array onto the result object is gated on CER-002.
- **AC-6 PDF wiring** — rasterising the page and calling `judge_layout()` lives in the
  PDF processor. Not in Allowed Paths → CER-003. The `judge_layout()` method itself is
  in scope; its call site is not (avoid shipping it orphaned — see CLAUDE.md learning).
- No frontend / UI work (classification Tasks Not Applicable 4.2, 5.1, 5.2).
- No opportunistic refactor of `translate_blocks_batch`, caching, or metrics paths.

## Required Changes

| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | `config.py` L120 | change `QE_ENABLED` default `"false"`→`"true"` | backend-engineer |
| IP-2 | `config.py` after L122 | add `QE_RESCORE_THRESHOLD: float = float(os.environ.get("QE_RESCORE_THRESHOLD", "0.5"))` (default owned by env contract, see Known Risks) | backend-engineer |
| IP-3 | `translation_service.py` critique loop L297-332 | after producing `_revised`, score `(src,draft)` vs `(src,revised)` via `score_blocks(model,[(s,draft),(s,revised)])`; adopt revised **iff `score(revised) >= score(draft)`**; exact tie keeps original (design Key Decisions: tie→keep original) | backend-engineer |
| IP-4 | `translation_service.py` critique loop | wrap QE model load/score in `try/except (ImportError, Exception)`; on unavailable fall back to deterministic length-ratio + fluency heuristic, same `>=` adoption + tie rule (AC-8) | backend-engineer |
| IP-5 | `quality_evaluator.py` | no new symbol required — `score_blocks` (L68-98) is the inline scorer; expose a thin lazy `load_model`+`score_blocks` helper if the gate needs one call site | backend-engineer |
| IP-6 | `quality_judge.py` `evaluate` L116-158 | add `judge_block(src, tgt) -> dict` (or reuse `evaluate`) and refactor `_run_judge_loop_impl` L234-293 to score **per block** instead of the whole-doc join at L238-239 (design Per-block judge — Approach A) | backend-engineer |
| IP-7 | `quality_judge.py` new method | add `judge_layout(page_image, ...) -> int` (range 1-5) taking an **in-memory PIL image** (never a path), reusing the local Gemma `self._client`; `JUDGE_ENABLED` stays false (AC-6) | backend-engineer |
| IP-8 | `translation_service.py` `translate_document` L446-516 | replace the bare `translate_blocks_batch` (L468) with a `translate_texts(...)` call per chunk so terms + critique + overlap context are inherited; map returned `tmap` back onto chunk elements; preserve BR-51 failure/placeholder + reassembly (L518-531) | backend-engineer |
| IP-9 | `translation_service.py` `translate_texts` + `translate_document` | thread the previous chunk's trailing 50-token overlap in as read-only context (reuse `context_prompts.build_context_prefix`, L262) so overlap is no longer dedup-only (AC-11) | backend-engineer |
| IP-10 | contracts (env/business/data) | see Contract Updates | contract-reviewer |
| IP-11 | tests | author/extend per Test Execution Plan; avoid wiring/selection/entry-point tautologies (CLAUDE.md) | test-strategist |
| IP-12 | (gated CER-002) `job_manager.py` | rescore routing for AC-2 + per-block judge persistence for AC-5 | backend-engineer |
| IP-13 | (gated CER-003) PDF processor | rasterise page → call `judge_layout` for AC-6 | backend-engineer |

## Source Artifact Pointers

| source | relevant pointer | used for |
|---|---|---|
| design.md | Key Decisions: critique gate score source / tie-handling | IP-3 adoption rule |
| design.md | Key Decisions: No-QE fallback heuristic | IP-4 fallback contract |
| design.md | Key Decisions: Per-segment QE call shape | IP-3/IP-5 one batched `score_blocks` call, not per-segment `predict` |
| design.md | Key Decisions: Per-block judge — Approach A | IP-6 reuse `evaluate()` per block |
| design.md | Key Decisions: MLLM layout scoring interface | IP-7 in-memory PIL only, local Gemma (BR-32 / ADR 0007) |
| design.md | Key Decisions: `translate_document()` wiring | IP-8/IP-9 delegate + overlap-as-context |
| change-classification.md | Inferred Acceptance Criteria AC-1..AC-11 | scope + test mapping |
| change-classification.md | Required Contracts | IP-10 contract surfaces |
| test-plan.md | AC→test mapping + Test Execution Ladder | phases + evidence |
| ci-gates.md | Required Gates table | verification gates |

## File-Level Plan

| path or glob | action | notes |
|---|---|---|
| `app/backend/config.py` | edit | IP-1 (L120), IP-2 (after L122) |
| `app/backend/services/quality_evaluator.py` | edit (maybe none) | IP-5 — `score_blocks` already returns `List[float]`; no signature change |
| `app/backend/services/translation_service.py` | edit | IP-3, IP-4 (critique loop L258-346); IP-8, IP-9 (`translate_document` L446-516) |
| `app/backend/services/quality_judge.py` | edit | IP-6 (`_run_judge_loop_impl` L234-293), IP-7 (new `judge_layout`) |
| `app/backend/services/context_prompts.py` | read-only | `build_context_prefix` (L262) reused by IP-9 |
| `contracts/env/env-contract.md` + `env.schema.json` + `.env.example.template` | edit | IP-10 env |
| `contracts/business/business-rules.md` | edit | IP-10 business |
| `contracts/data/data-shape-contract.md` | edit | IP-10 data |
| `contracts/api/api-contract.md` + `openapi.yml` | conditional | only if CER-001 confirmed (see Contract Updates) |
| `app/backend/services/job_manager.py` | **gated CER-002** | IP-12 — do not touch until approved |
| `app/backend/processors/pdf_processor.py` | **gated CER-003** | IP-13 — do not touch until approved |

## Contract Updates

- **API**: conditional. CER-001 — contract-reviewer confirms whether per-segment QE /
  per-block judge arrays extend `GET /jobs/{id}/quality` or `GET /judge` response schemas
  in `contracts/api/api-contract.md`. If yes: update the contract **and** run
  `cdd-kit openapi export --out contracts/api/openapi.yml` (commit it; stale openapi fails CI).
- **CSS/UI**: none.
- **Env**: `contracts/env/env-contract.md` — flip `QE_ENABLED` default row (currently L37,
  `false`→`true`, update note text); add a `QE_RESCORE_THRESHOLD` row (type float, documented
  default, validation, "ignored when QE_ENABLED=false"). Mirror in `env.schema.json` and
  `.env.example.template` (the `.env.example`/`env.schema` sync gate must stay green).
- **Data shape**: `contracts/data/data-shape-contract.md` — per-block judge score array shape,
  PDF MLLM layout score field (int 1-5, additive/optional), per-segment QE score structure.
- **Business logic**: `contracts/business/business-rules.md` — new BRs: QE rescore-threshold
  routing, critique adoption gate (`adopt iff revised ≥ original`, tie→original), no-QE fallback
  heuristic, per-block judge scoring, `translate_document()` long-doc parity guarantees.
- **CI/CD**: no new gate.

## Test Execution Plan

Required phase floor: collect → targeted → changed-area → contract (env/business/data
affected) → quality (if configured) → full. Implementation agents generate evidence with
`cdd-kit test run`; the gate validates `test-evidence.yml`. Full ladder in test-plan.md /
references/sdd-tdd-policy.md. Target the real seam, not a wrapper (CLAUDE.md tautology traps).

| acceptance criterion | test file / target | expected signal |
|---|---|---|
| AC-1 | tests/test_quality_evaluation.py | `score_blocks` returns one score per input pair (per-segment) |
| AC-2 (gated) | tests/test_quality_evaluation.py | segments `< QE_RESCORE_THRESHOLD` re-translated; others untouched (assert WHICH) |
| AC-3 | tests/test_env_contract.py | `QE_ENABLED` default true in config + env contract |
| AC-4 | tests/test_env_contract.py | `QE_RESCORE_THRESHOLD` present with documented default + schema |
| AC-5 | tests/test_quality_judge.py | judge emits per-block scores (assert per-block call/selection, not whole-doc join) |
| AC-6 | tests/test_quality_judge.py | `judge_layout(PIL.Image)` returns int 1-5; JUDGE_ENABLED still false |
| AC-7 | tests/test_translation_strategy.py | revised adopted iff `>= draft`; exact tie keeps original |
| AC-8 | tests/test_translation_strategy.py | QE-unavailable → heuristic gate; pipeline completes |
| AC-9 | tests/test_doc_chunker.py | `translate_document()` applies terms substitution (at real entry point) |
| AC-10 | tests/test_doc_chunker.py | `translate_document()` runs the critique loop |
| AC-11 | tests/test_context_window_segments.py | overlap fed as read-only context, not only dedup |

## Critical Ordering Constraints

1. IP-2 (`QE_RESCORE_THRESHOLD`) must land before IP-12 rescore routing references it.
2. `score_blocks` (IP-5, already present) must exist/import cleanly before IP-3 critique gate calls it.
3. IP-6 per-block `judge_block`/`evaluate` refactor must precede any AC-5 per-block persistence (IP-12).
4. IP-7 `judge_layout` method must exist before IP-13 PDF wiring (and IP-13 stays gated on CER-003).
5. IP-8 `translate_document` delegation relies on `translate_texts` already owning terms+critique
   (it does, L257-375); do IP-9 overlap-context after IP-8 delegation compiles.
6. Contract edits (IP-10) before the contract test phase; run `cdd-kit openapi export` only if CER-001 is yes.

## Context Expansion Requests (file before implementing gated items)

These paths are required to complete AC-2, AC-5 persistence, and AC-6 wiring but are
outside `context-manifest.md` Allowed Paths. Run `cdd-kit context request` and obtain
approval (`cdd-kit context approve`) before backend-engineer touches them.

- CER-001 (already noted in manifest, pending): `contracts/api/openapi.yml` — approve only if
  contract-reviewer confirms QE/judge response-schema change.
- CER-002 (new, pending): `app/backend/services/job_manager.py` — AC-2 rescore routing
  (post-translate QE hook L416-442) + AC-5 per-block `JudgeResult` storage (L43-57).
- CER-003 (new, pending): `app/backend/processors/pdf_processor.py` — AC-6 page rasterise →
  `judge_layout` call site.

## Handoff Constraints

- Implementation agents must not infer missing requirements from chat history.
- Do not re-copy full design, test strategy, CI policy, or contract prose into this plan; follow the source pointers above.
- If this plan omits a required file, behavior, contract, or test, stop and report `blocked`.
- Keep implementation within the file-level plan unless a Context Expansion Request is approved.
- Do NOT implement IP-12/IP-13 (AC-2, AC-5 persistence, AC-6 wiring) until CER-002/CER-003 are approved; report `blocked` rather than reaching into `job_manager.py` or `processors/`.

## Known Risks

- **`.cdd/code-map.yml` may lag edits** — it currently shows `score_blocks` already present
  (L68-98), matching source; re-run `cdd-kit code-map` after implementation.
- **VRAM/latency** (design Open Risks): `QE_ENABLED` default-on + inline critique gate loads
  COMET during translation; quantify in `qa-report.md` / `stress-soak-report.md`, gate to
  default-off if a blocking regression appears.
- **`QE_RESCORE_THRESHOLD` default** is model-scale dependent; the concrete value (`0.5`
  placeholder) is owned by the env contract and must be tuned, not guessed in code.
- **Orphaned `judge_layout`** — without CER-003 the method ships uncalled; track wiring as a
  follow-up so AC-6 is not falsely marked done (CLAUDE.md orphaned-component learning).
- **MLLM layout privacy** — `judge_layout` images go only to the local Gemma socket; must never
  route to a cloud provider (BR-32 / ADR 0007).
