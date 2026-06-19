# Change Classification

## Change ID
- p2-long-doc-chunking

## Change Types
- primary: feature-add (backend semantic chunking + Doc2Doc translation path)
- secondary: env-change (new `CHUNK_OVERLAP_TOKENS` var), business-logic-change (semantic boundary priority + reassembly ordering)

## Risk Level
- medium

## Impact Radius
- cross-module (new `doc_chunker.py` + `translation_service.py` Doc2Doc entry point + `config.py`/env; consumed by orchestrator/processors translation flow)

## Tier
- 2

## Lane
- feature

## Risk Summary
New correctness-critical text-processing logic: chunk boundaries, token-ceiling sizing, overlap, and original-order reassembly are all places where document content can be silently dropped, duplicated, or reordered. The change adds a new public service entry point (Doc2Doc) and a new env var, and must preserve the existing per-segment `translate_texts()` path unchanged (backward-compatibility constraint). No HTTP API surface, schema migration, auth, or persistence is touched, which keeps it below Tier 0/1; but the reassembly/overlap correctness and data-integrity risk keep it above isolated Tier 3/4. Classified at Tier 2 per "classify upward when in doubt."

## Architecture Review Required
- yes
- reason: Introduces a new module boundary (`doc_chunker.py`) and a new data-flow path (Doc2Doc) through `translation_service.py`. Non-obvious design decisions exist: chunker/service boundary, chunk IR/data shape, overlap-deduplication strategy on reassembly, and the contract for how chunking stays transparent to callers while `translate_texts()` stays unchanged. These boundary and data-flow decisions need `spec-architect` to write `design.md` before planning.

## Required Artifacts
Always required: change-request.md, change-classification.md, implementation-plan.md, test-plan.md, ci-gates.md, tasks.yml, context-manifest.md

## Optional Artifacts

| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | Existing `translate_texts()` behavior is being preserved; contrast inline in design.md |
| proposal.md | no | Scope is well-defined in the change request |
| spec.md | no | Behavior fits in design.md + implementation-plan.md |
| design.md | yes | Architecture Review Required = yes (new module boundary + Doc2Doc data-flow + overlap/reassembly strategy) |
| qa-report.md | no | Routine pass/fail evidence fits in agent-log/qa-reviewer.yml |
| regression-report.md | no | Backward-compat guarded by unchanged-path test; promote only if regression found |
| visual-review-report.md | no | No UI output |
| monkey-test-report.md | no | No interactive UI surface |
| stress-soak-report.md | no | Per-chunk single LLM calls; not a high-load/soak surface at this tier |

## Required Contracts
- API: none (Doc2Doc is an internal service method, not a new HTTP endpoint; confirm in planning — if exposed over HTTP, add api-contract.md + openapi export)
- CSS/UI: none
- Env: contracts/env/env-contract.md (+ .env.example.template, env.schema.json) — new CHUNK_OVERLAP_TOKENS var
- Data shape: contracts/data/data-shape-contract.md — chunk representation and Doc2Doc input/output document shape
- Business logic: contracts/business/business-rules.md — semantic boundary priority, chunk-size ceiling, overlap rule, original-order reassembly
- CI/CD: none

## Required Tests
- unit: yes — doc_chunker.py boundary detection (paragraph/heading/sentence priority), token-ceiling sizing, overlap insertion, reassembly preserves original order
- contract: yes — env contract test for CHUNK_OVERLAP_TOKENS; business-rule conformance for boundary priority ordering
- integration: yes — Doc2Doc path end-to-end (split → translate-each → reassemble) with mocked LLM client; assert translate_texts() path unchanged
- E2E: no
- visual: no
- data-boundary: yes — oversized atomic segment, empty doc, single-chunk doc (token count at ceiling), mixed line endings — must not drop or duplicate content
- resilience: yes — single chunk translation failure must surface without corrupting reassembly of remaining chunks
- fuzz/monkey: no
- stress: no
- soak: no

## Required Agents
1. spec-architect — write design.md (module boundary, chunk data shape, overlap/reassembly strategy, Doc2Doc contract)
2. implementation-planner — turn design + contracts + tests into the execution packet
3. backend-engineer — implement doc_chunker.py and translation_service.py Doc2Doc path + config/env wiring
4. test-strategist — author unit/integration/data-boundary/resilience tests and the acceptance-criteria → test mapping
5. contract-reviewer — verify env / data-shape / business contract updates match implementation
6. qa-reviewer — release readiness, regression on unchanged translate_texts() path, gate confirmation

## Inferred Acceptance Criteria
- AC-1: Given a document whose token count exceeds `num_ctx`, the chunker splits it so that every chunk's token count (including overlap) is within the `num_ctx` ceiling.
- AC-2: Boundary selection follows priority paragraph break > section heading > sentence boundary; a higher-priority boundary is always preferred when available within the size budget.
- AC-3: Adjacent chunks share overlap of `CHUNK_OVERLAP_TOKENS` tokens (configurable via env), defaulting to a documented value when unset.
- AC-4: Each chunk is translated in a single LLM call, independently of the others.
- AC-5: Reassembly produces a single translated document in the original chunk order, with no content dropped, duplicated, or reordered (overlap regions are de-duplicated, not emitted twice).
- AC-6: A document whose token count is at or below `num_ctx` produces exactly one chunk and one LLM call (no unnecessary splitting).
- AC-7: The Doc2Doc entry point on `translation_service.py` accepts a whole document and returns a translated document with chunking applied transparently — no caller-side pre-splitting required.
- AC-8: The existing per-segment `translate_texts()` path produces identical behavior to before this change (no regression).

## Tasks Not Applicable
- not-applicable: 2.2 (CSS/UI contract), 2.6 (CI/CD contract), 4.2 (frontend implementation), 5.1 (UI/UX review), 5.2 (visual review), 3.4 (monkey tests), 3.5 (stress/soak tests)

## Clarifications or Assumptions
- Assumption: Doc2Doc path is an internal method on translation_service.py, not a new HTTP endpoint. If exposed over HTTP, promote to include api-contract.md + openapi export.
- Assumption: Token counting reuses the existing num_ctx tokenizer mechanism (completed in P1); no new tokenizer introduced.
- Assumption: CHUNK_OVERLAP_TOKENS is a non-secret tuning var with a sane documented default.
- Open for spec-architect: overlap de-duplication on reassembly strategy (drop overlap from second chunk's output, or align on shared boundary) must be pinned in design.md and business-rules.md so AC-5 is testable.
- Watch for cdd-kit gate tier-floor false-positives on env/"endpoint"/"integration" vocabulary — use tier-floor-override with rationale if the gate forces Tier 0/2 spuriously.

## Context Manifest Draft
(see context-manifest.md — written from this draft)
