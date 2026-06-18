# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- backend parsers (`app/backend/parsers/`)
- IR model (`app/backend/models/translatable_document.py`)
- dependency manifest (`app/backend/requirements.txt`, `app/backend/environment.yml`)
- env contract (`contracts/env/env-contract.md`) — new model path env var
- data-shape contract (`contracts/data/data-shape-contract.md`) — IR region type
- business rules (`contracts/business/business-rules.md`) — local-inference privacy constraint
- CI gates (`contracts/ci/ci-gate-contract.md`)
- golden regression tests (`tests/fixtures/golden/`, `tests/test_golden_regression.py`)

## Allowed Paths
- specs/changes/p2-layout-detection/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/parsers/
- app/backend/models/translatable_document.py
- app/backend/models/__init__.py
- app/backend/processors/pdf_processor.py
- app/backend/requirements.txt
- app/backend/environment.yml
- app/backend/config.py
- contracts/env/env-contract.md
- contracts/env/env.schema.json
- contracts/data/data-shape-contract.md
- contracts/business/business-rules.md
- contracts/ci/ci-gate-contract.md
- tests/fixtures/golden/
- tests/test_layout_detector.py
- tests/test_golden_regression.py
- tests/test_pdf_parser.py
- tests/test_translatable_document.py
- tests/test_ir_pipeline_decoupling.py
- tests/test_env_contract.py
- tests/__init__.py
- .github/workflows/contract-driven-gates.yml
- docs/adr/0002-ir-elementtype-serialized-values.md

## Required Contracts
- contracts/env/env-contract.md (新增 `LAYOUT_DETECTOR_MODEL_PATH` env var)
- contracts/data/data-shape-contract.md (IR region type `ElementType` 擴充確認)
- contracts/business/business-rules.md (本地推論隱私邊界規則)
- contracts/ci/ci-gate-contract.md (CI gate 更新)

## Required Tests
- tests/test_pdf_parser.py (新 layout detector 整合測試)
- tests/test_golden_regression.py (黃金樣本新舊雙跑)
- tests/test_translatable_document.py (IR 相容性)
- tests/test_ir_pipeline_decoupling.py (解耦驗證)

## Agent Work Packets

### change-classifier
- specs/changes/p2-layout-detection/
- specs/context/project-map.md
- specs/context/contracts-index.md

### contract-reviewer
- specs/changes/p2-layout-detection/
- contracts/env/env-contract.md
- contracts/env/env.schema.json
- contracts/data/data-shape-contract.md
- contracts/business/business-rules.md
- contracts/ci/ci-gate-contract.md

### test-strategist
- specs/changes/p2-layout-detection/
- app/backend/parsers/pdf_parser.py
- app/backend/models/translatable_document.py
- tests/test_pdf_parser.py
- tests/test_golden_regression.py
- tests/test_translatable_document.py
- tests/test_ir_pipeline_decoupling.py
- tests/fixtures/golden/

### spec-architect
- specs/changes/p2-layout-detection/
- app/backend/parsers/
- app/backend/models/translatable_document.py
- app/backend/processors/pdf_processor.py
- app/backend/config.py
- contracts/data/data-shape-contract.md
- contracts/env/env-contract.md

### ci-cd-gatekeeper
- specs/changes/p2-layout-detection/
- .github/workflows/contract-driven-gates.yml
- contracts/ci/ci-gate-contract.md

### implementation-planner
- specs/changes/p2-layout-detection/
- app/backend/parsers/
- app/backend/models/translatable_document.py
- app/backend/processors/pdf_processor.py
- app/backend/config.py
- app/backend/requirements.txt
- contracts/

### backend-engineer
- specs/changes/p2-layout-detection/
- app/backend/parsers/
- app/backend/models/translatable_document.py
- app/backend/processors/pdf_processor.py
- app/backend/config.py
- app/backend/requirements.txt
- app/backend/environment.yml
- tests/test_layout_detector.py
- tests/test_pdf_parser.py
- tests/test_golden_regression.py
- tests/test_translatable_document.py
- tests/test_ir_pipeline_decoupling.py
- tests/test_env_contract.py
- tests/fixtures/golden/
- contracts/env/env-contract.md
- contracts/env/env.schema.json
- contracts/data/data-shape-contract.md

### dependency-security-reviewer
- specs/changes/p2-layout-detection/
- app/backend/requirements.txt
- app/backend/environment.yml

### qa-reviewer
- specs/changes/p2-layout-detection/
- contracts/

## Context Expansion Requests
-

## Approved Expansions
-
