# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- Backend routing: `app/backend/services/model_router.py` (routing table + `resolve_route_groups()`)
- Provider config: `config/providers.yml` (`routing:` section as source of truth)
- Business behavior contract: routing rule semantics

## Allowed Paths
- specs/changes/p1-provider-routing/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/services/model_router.py
- config/providers.yml
- config/providers.yml.example
- contracts/business/business-rules.md
- tests/test_model_router.py
- docs/adr/0001-config-driven-provider-registry.md
- app/backend/processors/orchestrator.py
- app/backend/services/translation_service.py

## Required Contracts
- contracts/business/business-rules.md

## Required Tests
- tests/test_model_router.py

## Agent Work Packets

### change-classifier
- specs/changes/p1-provider-routing/
- specs/context/project-map.md
- specs/context/contracts-index.md

### contract-reviewer
- specs/changes/p1-provider-routing/
- contracts/business/business-rules.md
- config/providers.yml

### test-strategist
- specs/changes/p1-provider-routing/
- tests/test_model_router.py
- app/backend/services/model_router.py
- config/providers.yml

### implementation-planner
- specs/changes/p1-provider-routing/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/services/model_router.py
- config/providers.yml
- contracts/business/business-rules.md
- docs/adr/0001-config-driven-provider-registry.md

### backend-engineer
- specs/changes/p1-provider-routing/
- app/backend/services/model_router.py
- config/providers.yml
- config/providers.yml.example
- tests/test_model_router.py
- contracts/business/business-rules.md

### qa-reviewer
- specs/changes/p1-provider-routing/
- tests/test_model_router.py
- contracts/business/business-rules.md

## Context Expansion Requests

- request-id: CER-001
  requested_paths:
    - app/backend/processors/orchestrator.py
    - app/backend/services/translation_service.py
  reason: Contract-reviewer flagged that per-language routing may return multiple RouteGroups in the cloud path, which could break callers that assume exactly one group. These files must be checked before backend-engineer implements resolve_route_groups() changes.
  status: approved

## Approved Expansions
- CER-001 approved: orchestrator.py + translation_service.py added to Allowed Paths; contract-reviewer confirmed behavioral risk on resolve_route_groups() return shape.
