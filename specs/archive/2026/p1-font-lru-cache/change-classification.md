# Change Classification

## Change Types
- primary: performance-optimization
- secondary: refactor

## Lane
- feature

## Risk Level
- low

## Impact Radius
- module-level (app/backend/renderers/pdf_generator.py font-loading path only)

## Tier
- 4

## Architecture Review Required
- no
- reason: Module-local LRU cache is an established pattern; no module boundaries, data flow, or compatibility decisions are affected.

## Required Artifacts
Always required: change-request.md, change-classification.md, implementation-plan.md, test-plan.md, ci-gates.md, tasks.yml, context-manifest.md

## Optional Artifacts (default: no — set yes only with explicit reason)

| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | Current behavior (per-call disk read) fully described in change-request.md. |
| proposal.md | no | No product-facing decision; mechanical internal cache. |
| spec.md | no | No spec-level behavior change. |
| design.md | no | No architecture review; module-local LRU cache is an obvious pattern. |
| qa-report.md | no | Pass/fail fits in agent-log; no blocking-finding prose expected. |
| regression-report.md | no | Existing test suite is the regression guard. |
| visual-review-report.md | no | No UI surface. |
| monkey-test-report.md | no | Not applicable. |
| stress-soak-report.md | no | Caching micro-optimization does not warrant soak prose. |

## Required Contracts
- API: none
- CSS/UI: none
- Env: none
- Data shape: none
- Business logic: none
- CI/CD: none

Caller-visible behavior of `_insert_text_in_rect` is unchanged; only internal I/O is reduced.

## Required Tests
- unit: yes — verify second call for same font path does not trigger disk I/O; verify cached buffer equality; verify distinct paths cached independently; verify error-path behavior unchanged
- contract: none
- integration: none
- E2E: none
- visual: none
- data-boundary: none
- resilience: none
- fuzz/monkey: none
- stress: none
- soak: none

## Required Agents
1. `contract-reviewer` — confirm no contracts are touched
2. `test-strategist` — plan the no-second-disk-read unit test and regression guard
3. `ci-cd-gatekeeper` — gate plan
4. `implementation-planner` — execution packet (cache key, eviction policy, thread-safety stance, test-clear hook)
5. `backend-engineer` — implement module-level LRU/font-buffer cache; write failing tests first
6. `qa-reviewer` — release readiness, full-suite pass confirmation

## Inferred Acceptance Criteria
- AC-1: The first call to `_insert_text_in_rect` for a given font path reads the font file from disk exactly once.
- AC-2: A second (and subsequent) call for the same font path retrieves the buffer from the in-memory cache and does NOT perform a disk read.
- AC-3: Distinct font paths are cached independently (each read from disk once on first use).
- AC-4: The rendered output for cached vs. uncached paths is byte-equivalent — caching introduces no caller-visible behavior change.
- AC-5: The full existing test suite continues to pass after the change.

## Tasks Not Applicable
- not-applicable: 1.3, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 3.2, 3.3, 3.4, 3.5, 4.2, 5.1, 5.2

## Risk Factors
- Module-level mutable cache introduces process-global state — potential cross-test bleed if the cache is not resettable between tests.
- Thread-safety: if `_insert_text_in_rect` is called concurrently, an unguarded cache could race on first population. Low likelihood but requires a deliberate decision.
- Cache key correctness: keying on path string could miss-hit if relative and absolute paths refer to the same file.

## Clarifications or Assumptions
- Target file is `app/backend/renderers/pdf_generator.py`.
- Existing test file is `tests/test_pdf_generator.py`.
- Error-path behavior (missing/unreadable font) must remain unchanged and must not cache poisoned/empty buffers.
- Tests must be able to reset/clear the cache between cases to avoid state bleed.
