# CI/CD Gate Review

## Change ID
term-extraction-db-first

## Required Gates for This Change

| gate name | tier | required | trigger | command / workflow | artifact |
|---|---:|---|---|---|---|
| contract-validation | 1 | required | push, pull_request | `cdd-kit validate --contracts` | none |
| dead-import-assertion | 1 | required | push, pull_request | `grep -rn --include="*.py" -E "(pgvector\|chromadb\|faiss\|hnswlib)" app/backend/services/term_extractor.py` — must return no match | none |
| dead-reference-ollama | 1 | required | push, pull_request | `grep -n "OLLAMA_BASE_URL" app/backend/services/term_extractor.py` — must return no match in extraction flow (translation path) | none |
| env-sync-panjit-embedding | 1 | required | push, pull_request | `grep -q "TERM_EMBEDDING_MODEL\|TERM_EMBEDDING_THRESHOLD\|TERM_EXTRACTION_MODEL" contracts/env/.env.example.template && grep -q "TERM_EMBEDDING_MODEL\|TERM_EMBEDDING_THRESHOLD\|TERM_EXTRACTION_MODEL" contracts/env/env.schema.json` | none |
| targeted-term-tests | 1 | required | push, pull_request | `pytest tests/test_term_extractor.py tests/test_term_db.py -x -q --tb=short` | test-results/targeted-term.xml |
| full-test-suite | 1 | required | push, pull_request | `pytest tests/ -x -q --tb=short --junitxml=test-results/junit.xml` | test-results/junit.xml |
| change-gate | 0 | required | local pre-PR | `cdd-kit gate term-extraction-db-first` | none |
| secret-scan | 1 | required | push, pull_request | `! grep -rn --include="*.py" --include="*.yml" -E "PANJIT_API\s*[:=]\s*[A-Za-z0-9+/]{20,}" .` | none |
| full-regression (PR) | 2 | informational | pull_request | `pytest tests/ -q --tb=short --junitxml=test-results/full-regression.xml` in `full-regression` job | test-results/full-regression.xml |

## Acceptance Criteria Covered by Each Gate

| gate name | ACs covered | test-plan.md reference |
|---|---|---|
| contract-validation | AC-4 (PANJIT endpoint config), AC-5 (threshold config), AC-8 (no Ollama in flow) | change-classification.md §Required Contracts |
| dead-import-assertion | AC-6 (no vector-DB package) | change-classification.md §Inferred Acceptance Criteria AC-6 |
| dead-reference-ollama | AC-8 (Ollama removed from extraction path), AC-2 (never calls localhost:11434) | change-classification.md §Inferred Acceptance Criteria AC-2, AC-8 |
| env-sync-panjit-embedding | AC-5 (configurable threshold), AC-4 (embedding model name in sync artifacts) | env-contract.md §Deployment Sync Policy |
| targeted-term-tests | AC-1 (DB hit skips extraction), AC-2 (DB miss calls PANJIT then saves), AC-3 (embedding failure skips injection), AC-5 (threshold boundary) | change-classification.md §Required Tests (unit, contract) |
| full-test-suite | All ACs — regression across full backend | change-classification.md §Required Tests (integration, data-boundary, resilience) |
| change-gate | All ACs — cdd-kit gate runs all contract validators + tier checks | change-classification.md §Tier |

## Workflow Changes Applied

The following gates are already satisfied by the existing `contract-and-fast-tests` job and `full-regression` job in `.github/workflows/contract-driven-gates.yml`:

- `cdd-kit validate --contracts` (contract-validation gate) — step "Validate contracts" in `contract-and-fast-tests`
- `pytest tests/ -x -q` (full-test-suite gate) — step "Unit, contract, integration, resilience, data-boundary tests" in `contract-and-fast-tests`
- `pytest tests/ -q` (full-regression gate) — `full-regression` job

New steps that must be added to `contract-and-fast-tests` when this change becomes the active gate:

1. **Dead-import assertion** — verify no vector-DB packages imported in term_extractor.py
2. **Dead-reference-ollama** — verify OLLAMA_BASE_URL removed from term extraction path
3. **Env sync — TERM_EMBEDDING_MODEL and TERM_EMBEDDING_THRESHOLD** — verify new vars present in .env.example.template and env.schema.json
4. **Targeted term tests** — fast-fail pytest on test_term_extractor.py + test_term_db.py before full suite
5. **Change gate** — `cdd-kit gate term-extraction-db-first`

### Deferred: workflow file edit

DO NOT modify `.github/workflows/contract-driven-gates.yml` yet. The current active gate is `fallback-chain-cloud-providers` (line 48 of contract-driven-gates.yml). Only one change gate can be active at a time.

The workflow edit — replacing `cdd-kit gate fallback-chain-cloud-providers` with `cdd-kit gate term-extraction-db-first` and adding the new steps above — must happen as part of the same PR that removes `fallback-chain-cloud-providers` from the active gate slot (i.e., after that change is archived).

## Promotion Policy

When `fallback-chain-cloud-providers` is closed and archived:

1. Run `/cdd-close fallback-chain-cloud-providers` to archive that change.
2. Remove the `cdd-kit gate fallback-chain-cloud-providers` step from `.github/workflows/contract-driven-gates.yml` (per CLAUDE.md learned lesson: archived dirs no longer exist under `specs/changes/` and CI fails with "change not found").
3. Add `cdd-kit gate term-extraction-db-first` in its place.
4. Add the four new steps (dead-import, dead-reference-ollama, env-sync, targeted-term-tests) to the `contract-and-fast-tests` job.
5. Commit the workflow change together with or immediately before the first implementation commit for this change.

## Rollback Policy

- All gates are stateless grep/pytest assertions. No migration or data-shape change that cannot be reverted by reverting the PR.
- PANJIT embedding calls are non-destructive; term_db writes are additive (new terms saved, existing unchanged). Rolling back removes the write path; pre-existing DB rows are inert.
- Rollback trigger: any Tier 1 gate failure on main after merge. Revert the merge commit; no DDL rollback needed.
- `OLLAMA_BASE_URL` remains in env-contract.md (used by layout_detector.py); removing this change does not disturb that contract row.

## Merge Eligibility

blocked — pending `fallback-chain-cloud-providers` archival and workflow promotion step above.

Once the promotion is applied and all Tier 1 gates pass on the PR:

- `contract-and-fast-tests` — required (blocks merge)
- `full-regression` — informational on PR; escalates to blocker if new failures introduced
- `golden-sample-regression` — required (pre-existing gate, unaffected by this change)
- `layout-detector-dependency-gate` — required (pre-existing gate, unaffected by this change)

## Notes

- The dead-import assertion uses a `!` inversion: grep returning no match exits 1, `!` flips to 0 (pass). A match exits 0, `!` flips to 1 (fail). This is the same pattern as `layout-detector-dependency-gate` in the existing workflow.
- `OLLAMA_BASE_URL` grep targets only `app/backend/services/term_extractor.py`, not the full repo. `layout_detector.py` legitimately retains an Ollama reference; the gate must not flag it.
- No openapi.yml regeneration is required: this change adds no served HTTP route. The existing `cdd-kit openapi export --check` step is unaffected.
- Env vars introduced by this change (`TERM_EMBEDDING_MODEL`, `TERM_EMBEDDING_THRESHOLD`) must appear in `contracts/env/env-contract.md`, `contracts/env/.env.example.template`, and `contracts/env/env.schema.json` in the same PR per env-contract.md §Deployment Sync Policy.
- Neither `TERM_EMBEDDING_MODEL` nor `TERM_EMBEDDING_THRESHOLD` are secrets; the secret-scan grep pattern is unchanged.
- Tier 3 (nightly real-infra) and Tier 4/5 (weekly soak/stress) are not applicable per change-classification.md §Tasks Not Applicable 3.4, 3.5, 6.4.
