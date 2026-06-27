# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- Table structure recognition (parsers module)

## Allowed Paths
- specs/changes/tatr-parse-outputs/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/parsers/table_recognizer.py
- app/backend/models/translatable_document.py
- app/backend/config.py
- tests/test_table_recognizer.py
- contracts/data/data-shape-contract.md

## Required Contracts
- contracts/data/data-shape-contract.md (review-only; no edit expected)

## Required Tests
- tests/test_table_recognizer.py

## Agent Work Packets

### change-classifier
- specs/changes/tatr-parse-outputs/
- specs/context/project-map.md
- specs/context/contracts-index.md

### implementation-planner
- specs/changes/tatr-parse-outputs/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/parsers/table_recognizer.py
- app/backend/models/translatable_document.py
- app/backend/config.py

### backend-engineer
- specs/changes/tatr-parse-outputs/
- app/backend/parsers/table_recognizer.py
- app/backend/models/translatable_document.py
- app/backend/config.py

### test-strategist
- specs/changes/tatr-parse-outputs/
- tests/test_table_recognizer.py
- app/backend/parsers/table_recognizer.py
- app/backend/models/translatable_document.py

### contract-reviewer
- specs/changes/tatr-parse-outputs/
- contracts/data/data-shape-contract.md
- app/backend/models/translatable_document.py

### qa-reviewer
- specs/changes/tatr-parse-outputs/
- tests/test_table_recognizer.py
- app/backend/parsers/table_recognizer.py

## Context Expansion Requests
-

## Approved Expansions
-
