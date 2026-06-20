# Context Manifest — download-url-in-jobstatus

## Affected Surfaces
- backend API response schema (JobStatus)
- backend job lifecycle service (job_manager)
- API contract (api-contract.md / openapi.yml)

## Allowed Paths
- specs/changes/download-url-in-jobstatus/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/api/schemas.py
- app/backend/api/routes.py
- app/backend/services/job_manager.py
- app/frontend/src/pages/TranslatePage.jsx
- contracts/api/api-contract.md
- contracts/api/openapi.yml
- contracts/api/openapi.json
- tests/

## Required Contracts
- contracts/api/api-contract.md
- contracts/api/openapi.yml (regenerated artifact)

## Context Expansion Requests
- CER-001: tests/contract/response-samples.json — confirm whether a JobStatus response sample exists that must be updated. Status: pending.
