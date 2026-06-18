# Change Classification

## Change Types
- primary: feature-add (four-state term lifecycle, new API endpoints, new TermDB methods)
- secondary: bug-fix (injection gate closes `confidence=1.0` trust bypass)

## Risk Level
- medium
- reason: removing `confidence=1.0` bypass from injection gate changes runtime injection behavior for all existing `unverified` terms. Low blast radius (local SQLite only) but visible to any workflow relying on high-confidence unverified terms being auto-injected. Opt-in escape hatch (`TERM_INJECT_HIGH_CONFIDENCE_UNVERIFIED`) mitigates migration risk.

## Impact Radius
- module-level (term_db.py, term_extractor.py, schemas.py, routes.py, config.py, models/term.py)

## Tier
- 2
- tier-floor-override: "endpoint" in scope, but these are CRUD admin endpoints for a local SQLite term-DB, not a shared cache, auth system, or integration with external services. No deployment risk, no data residency concern. Tier 2 is correct.

## Architecture Review Required
- no

## Required Artifacts
Always required: change-request.md, change-classification.md, implementation-plan.md, test-plan.md, ci-gates.md, tasks.yml, context-manifest.md

## Optional Artifacts (default: no — set yes only with explicit reason)
| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | |
| proposal.md | no | |
| spec.md | no | |
| design.md | no | |
| qa-report.md | no | |
| regression-report.md | no | |
| visual-review-report.md | no | |
| monkey-test-report.md | no | |
| stress-soak-report.md | no | |

## Required Contracts
- API: add `/terms/reject` + `/terms/flag-needs-review`; extend `/terms/export` status param; extend `TermStatsResponse` with `by_status`
- CSS/UI: none
- Env: add `TERM_INJECT_HIGH_CONFIDENCE_UNVERIFIED` (bool, default false), `TERM_INJECT_CONF_THRESHOLD` (float, default 0.9)
- Data shape: `TermStatsResponse` schema change (additive: new fields); `Term.status` valid-value list update
- Business logic: document 4-state machine, injection gate rule, source-weight cap, `rejected` protection in conflict strategies
- CI/CD: none (existing contract-validate + pytest gates sufficient)

## Required Tests
- unit: injection gate (AC-1..AC-3), state transitions (AC-4), conflict strategy protection (AC-5), stats (AC-6), confidence cap (AC-8)
- contract: `TermStatsResponse` shape includes `by_status`; export endpoint accepts `needs_review` + `rejected` status values
- integration: `/terms/reject` and `/terms/flag-needs-review` round-trip via TermDB; verify injected set excludes rejected/needs_review after API call
- E2E: not required (Tier 2)
- visual: not applicable
- data-boundary: insert `rejected` term then attempt injection → assert not in result set
- resilience: not required (Tier 2)
- fuzz/monkey: not required
- stress: not required
- soak: not required

## Required Agents
- contract-reviewer (API + env + data-shape + business-logic contracts)
- backend-engineer (IP-1..IP-10)
- test-strategist (test-plan)
- qa-reviewer (gate check)

## Inferred Acceptance Criteria

- AC-1: `get_top_terms()` and `get_document_terms()` never return terms with `status='rejected'` or `status='needs_review'`
- AC-2: Default injection gate: `unverified` terms with `confidence=1.0` are NOT injected when `TERM_INJECT_HIGH_CONFIDENCE_UNVERIFIED=false` (which is the default)
- AC-3: Optional loose gate: with `TERM_INJECT_HIGH_CONFIDENCE_UNVERIFIED=true` and `TERM_INJECT_CONF_THRESHOLD=0.9`, `unverified` terms with `confidence >= 0.9` ARE included in injection results
- AC-4: `TermDB.reject()` transitions any existing term to `status='rejected'`; `TermDB.flag_needs_review()` transitions `unverified` or `approved` term to `status='needs_review'`; both return `False` when term not found
- AC-5: `insert()` strategy `overwrite` and `merge` do NOT overwrite a `rejected` term (same protection as `approved`); strategy `force` can overwrite `rejected`
- AC-6: `TermDB.get_stats()` returns a `by_status` dict with integer counts for all four statuses (`unverified`, `needs_review`, `approved`, `rejected`)
- AC-7: `POST /terms/reject` and `POST /terms/flag-needs-review` return HTTP 200 on success and HTTP 404 when term not found; `GET /terms/export` accepts `status=needs_review` and `status=rejected` without error
- AC-8: LLM-extracted confidence is capped at 0.85 in `term_extractor.py`; `contracts/business/business-rules.md` documents the 4-state machine, injection gate, and confidence-source weighting; existing 389 test baseline passes

## Tasks Not Applicable
- not-applicable: 1.3, 2.2, 3.3, 3.4, 3.5, 4.2, 4.3, 5.1, 5.2, 6.4

## Clarifications or Assumptions
- `needs_review` transition sources: manual API call only for P1 (no auto-flag logic)
- `approve()` existing method at term_db.py:294 works for all four source statuses — no change needed to its SQL
- `edit_term()` at term_db.py:261 sets `status='approved'` directly; this remains correct (editing a term is an implicit approval)
- `_dict_to_term()` default `status='approved'` for file imports is intentional and stays (human-curated data)

## Context Manifest Draft

### Affected Surfaces
- `app/backend/models/term.py` (Term.status field comment)
- `app/backend/services/term_db.py` (injection gate, new methods, stats, conflict strategy)
- `app/backend/services/term_extractor.py` (confidence cap)
- `app/backend/config.py` (new env vars)
- `app/backend/api/schemas.py` (TermStatsResponse, new TermRejectRequest)
- `app/backend/api/routes.py` (new endpoints, export filter)
- `contracts/business/business-rules.md` (state machine + injection gate rules)
- `contracts/env/env-contract.md` (new env vars)
- `contracts/api/api-contract.md` (new endpoints + TermStatsResponse schema)

### Allowed Paths
- specs/changes/p1-term-state-machine/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/models/term.py
- app/backend/services/term_db.py
- app/backend/services/term_extractor.py
- app/backend/config.py
- app/backend/api/schemas.py
- app/backend/api/routes.py
- contracts/business/business-rules.md
- contracts/env/env-contract.md
- contracts/api/api-contract.md
- contracts/data/data-shape-contract.md
- tests/

### Agent Work Packets

#### change-classifier
- specs/changes/p1-term-state-machine/
- specs/context/project-map.md
- specs/context/contracts-index.md

#### contract-reviewer
- specs/changes/p1-term-state-machine/
- app/backend/api/schemas.py
- app/backend/api/routes.py
- app/backend/config.py
- contracts/business/business-rules.md
- contracts/env/env-contract.md
- contracts/api/api-contract.md
- contracts/data/data-shape-contract.md

#### test-strategist
- specs/changes/p1-term-state-machine/
- app/backend/models/term.py
- app/backend/services/term_db.py
- app/backend/services/term_extractor.py
- app/backend/api/routes.py
- tests/

#### backend-engineer
- specs/changes/p1-term-state-machine/
- app/backend/models/term.py
- app/backend/services/term_db.py
- app/backend/services/term_extractor.py
- app/backend/config.py
- app/backend/api/schemas.py
- app/backend/api/routes.py
- contracts/business/business-rules.md
- contracts/env/env-contract.md
- contracts/api/api-contract.md

#### qa-reviewer
- specs/changes/p1-term-state-machine/
- tests/
