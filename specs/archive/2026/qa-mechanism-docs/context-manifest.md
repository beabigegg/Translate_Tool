# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- QA/quality-pipeline documentation across three contract surfaces (business/domain, api, data)

## Allowed Paths
- specs/changes/qa-mechanism-docs/
- specs/context/project-map.md
- specs/context/contracts-index.md
- contracts/business/business-rules.md
- contracts/api/api-contract.md
- contracts/api/openapi.yml
- contracts/api/openapi.json
- contracts/data/data-shape-contract.md
- docs/adr/0005-judge-rerender-apply.md
- docs/adr/0009-legacy-conversion-disclosure-and-qe-boundary.md

By the time this change's agents run, its three `depends-on` siblings are
fully planned (not yet implemented), so BR-98/99/100 and BR-92's retirement
exist only in those siblings' own `design.md`/`change-request.md` files, NOT
yet in the live `contracts/business/business-rules.md` — that landing only
happens when those siblings' `backend-engineer` passes run. Agents on THIS
change must therefore be briefed in-prompt with the finalized sibling
decisions (see change-request.md's "Sibling Decisions" section) rather than
reading the live contract file expecting to find BR-98/99/100 already there.

## Required Contracts
- contracts/business/business-rules.md
- contracts/api/api-contract.md
- contracts/data/data-shape-contract.md

## Required Tests
- none (documentation-only, no schema change)

## Agent Work Packets

### change-classifier
- specs/changes/qa-mechanism-docs/
- specs/context/project-map.md
- specs/context/contracts-index.md

### contract-reviewer
- specs/changes/qa-mechanism-docs/
- contracts/business/business-rules.md
- contracts/api/api-contract.md
- contracts/api/openapi.yml
- contracts/api/openapi.json
- contracts/data/data-shape-contract.md
- docs/adr/0005-judge-rerender-apply.md
- docs/adr/0009-legacy-conversion-disclosure-and-qe-boundary.md

### implementation-planner
- specs/changes/qa-mechanism-docs/
- specs/context/project-map.md
- specs/context/contracts-index.md
- contracts/business/business-rules.md
- contracts/api/api-contract.md
- contracts/data/data-shape-contract.md

### qa-reviewer
- specs/changes/qa-mechanism-docs/
- contracts/business/business-rules.md
- contracts/api/api-contract.md
- contracts/data/data-shape-contract.md

## Context Expansion Requests
- request-id: CER-001
  requested_paths:
    - specs/changes/br92-rescore-resolution/
    - specs/changes/qa-judge-provider-consistency/
    - specs/changes/qa-judge-hang-recovery/
    - specs/changes/batch-critique-qe-scoring/
    - specs/changes/translation-progress-detail-ui/
  reason: The cross-reference section must point at the sibling changes' final design/business-rule decisions. Requested by change-classifier.
  status: rejected — `.cdd/context-policy.json`'s `forbiddenPaths` baseline lists `specs/changes/*` as a HARD, non-overridable block, identical to the CER rejections already recorded in `qa-judge-hang-recovery`'s and `translation-progress-detail-ui`'s manifests this session. No CER can approve a cross-change `specs/changes/` read. Main Claude briefs contract-reviewer/implementation-planner directly, in-prompt, with the finalized sibling decisions (change-request.md's "Sibling Decisions" section) instead.

## Approved Expansions
-
