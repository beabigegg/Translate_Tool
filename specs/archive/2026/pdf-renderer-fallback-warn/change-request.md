# Change Request

## Original Request

Add a degraded warning flag to the job result when the fitz PDF renderer fails and falls back to ReportLab (item 0.5 of improvement plan).

Two warning paths:
1. When fitz rendering fails at pdf_processor.py:836-840 and ReportLab fallback is triggered — all images, backgrounds, and table lines are lost silently.
2. When PDF→DOCX routing trap hits at pdf_processor.py:376-414 — layout restoration is completely skipped and users don't know.

Add a `warnings: list[str]` field to the job result. Populate it in both paths. Update api/schemas.py and regenerate openapi.yml. Write a non-tautological test that mocks fitz failure at the call site and asserts warnings are present in the job result.

## Business / User Goal

Translators using the tool with PDF inputs cannot tell when quality has silently degraded. The fitz→ReportLab fallback and the PDF→DOCX routing path both silently discard visual fidelity. The job API response should expose this so clients (UI, integrations) can warn users.

## Non-goals

- Fixing the fitz failure itself
- Adding UI display of warnings (a future change)
- Adding warnings for non-PDF formats
- Redesigning the job model

## Constraints

- warnings field must be None/[] when no degradation occurs — no breakage of existing API consumers
- Must update contracts/api/api-contract.md and regenerate contracts/api/openapi.yml
- Tests must be non-tautological: mock at call site, not a wrapper

## Known Context

## Open Questions

## Requested Delivery Date / Priority
