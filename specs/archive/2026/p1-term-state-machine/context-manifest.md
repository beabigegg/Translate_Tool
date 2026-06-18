# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- `app/backend/models/term.py`
- `app/backend/services/term_db.py`
- `app/backend/services/term_extractor.py`
- `app/backend/config.py`
- `app/backend/api/schemas.py`
- `app/backend/api/routes.py`
- `contracts/business/business-rules.md`
- `contracts/env/env-contract.md`
- `contracts/api/api-contract.md`
- `contracts/data/data-shape-contract.md`
- `tests/test_term_state_machine.py` (new file)

## Allowed Paths
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

## Required Contracts
- contracts/business/business-rules.md (state machine + injection gate + confidence source rules)
- contracts/env/env-contract.md (TERM_INJECT_HIGH_CONFIDENCE_UNVERIFIED, TERM_INJECT_CONF_THRESHOLD)
- contracts/api/api-contract.md (new endpoints + TermStatsResponse schema)
- contracts/data/data-shape-contract.md (Term.status valid values)

## Required Tests
- tests/test_term_state_machine.py (8 new tests, AC-1..AC-8)

## Agent Work Packets

### change-classifier
- specs/changes/p1-term-state-machine/
- specs/context/project-map.md
- specs/context/contracts-index.md

### contract-reviewer
- specs/changes/p1-term-state-machine/
- app/backend/api/schemas.py
- app/backend/api/routes.py
- app/backend/config.py
- contracts/business/business-rules.md
- contracts/env/env-contract.md
- contracts/api/api-contract.md
- contracts/data/data-shape-contract.md

### test-strategist
- specs/changes/p1-term-state-machine/
- app/backend/models/term.py
- app/backend/services/term_db.py
- app/backend/services/term_extractor.py
- app/backend/api/routes.py
- tests/

### backend-engineer
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
- contracts/data/data-shape-contract.md
- tests/

### qa-reviewer
- specs/changes/p1-term-state-machine/
- tests/

## Context Expansion Requests
-

## Approved Expansions
-
