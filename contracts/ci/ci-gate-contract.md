---
contract: ci
summary: CI gate inventory, artifact retention, and rollback requirements.
owner: platform-team
surface: delivery-pipeline
schema-version: 0.2.0
last-changed: 2026-06-18
breaking-change-policy: deprecate-2-minors
---

# CI/CD Gate Contract

## Gate Inventory
| gate | tier | trigger | required | command/workflow | owner | artifact |
|---|---:|---|---:|---|---|---|
| contract-validate | 2+ | pre-commit / PR | yes | cdd-kit validate --contracts | platform-team | exit code 0 |
| change-gate | 2+ | pre-commit / PR | yes | cdd-kit gate <change-id> | platform-team | exit code 0 |
| unit-tests | 2+ | PR | yes | pytest tests/ | application-team | junit XML |
| golden-sample-regression | 2+ | PR | yes | pytest tests/test_golden_regression.py --tb=short -q | application-team | per-sample pass/fail diff (step log) |

## Required Check Policy

All gates in the Gate Inventory marked `required: yes` must pass before a PR is eligible to merge.

### golden-sample-regression gate

- **Scope**: runs the dual-run comparison framework over all samples in `tests/fixtures/golden/`. The framework parses each sample file with both old-format (pre-change) and new-format (post-change) code paths, serializes each resulting IR, and diffs the field-by-field output.
- **Offline constraint**: the gate must run with no network access and no GPU. All sample files are pre-committed fixtures; no external downloads occur at gate time.
- **Pass condition**: all samples produce field-by-field equivalent IR on both code paths for every field listed in the Round-trip guarantee in `contracts/data/data-shape-contract.md` (bbox coordinates, font metadata, element_type, reading_order, element_id, content, page_num, should_translate, translated_content, metadata).
- **Fail condition**: any sample where the new-format IR differs from the old-format IR on a pre-existing field (i.e., a field that existed before p2-ir-document-model) causes the gate to fail and blocks merge. Differences limited to the new `reading_order` field alone are not a regression.
- **Report artifact**: the gate emits a per-sample pass/fail diff to stdout (captured by CI as a step log). No external artifact store is required at Tier 2.
- **Sample set**: `tests/fixtures/golden/` must contain 3–5 representative files covering at minimum one PDF, one DOCX, and one PPTX. Files must be committed as binary fixtures; they must not be generated at CI time. Note: DOCX and PPTX binary fixtures are deferred pending sourcing of license-clean representative files; the gate skips DOCX/PPTX samples gracefully until they are committed.

## Informational Gate Promotion Policy

## Artifact Retention Policy

## Rollback Policy
