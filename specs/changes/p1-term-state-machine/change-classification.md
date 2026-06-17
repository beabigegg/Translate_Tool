# Change Classification

## Change Types
- primary:
- secondary:

## Risk Level
- low / medium / high / critical

## Impact Radius
- isolated / module-level / cross-module / system-wide

## Tier
- 0 / 1 / 2 / 3 / 4 / 5

## Architecture Review Required
- yes / no
- reason: (fill only if yes)
<!-- If yes, Optional Artifacts must set design.md to yes and Required Agents must include spec-architect. -->

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

Artifact minimization:
- Prefer optional `agent-log/*.yml` pointers for routine review evidence.
- Create report markdown only for blocking findings, approved-with-risk, visual evidence bundles, or high-risk load/soak results.
- Later artifacts should reference earlier artifacts by path/section/id instead of duplicating full content.

## Required Contracts
- API:
- CSS/UI:
- Env:
- Data shape:
- Business logic:
- CI/CD:

## Required Tests
- unit:
- contract:
- integration:
- E2E:
- visual:
- data-boundary:
- resilience:
- fuzz/monkey:
- stress:
- soak:

## Required Agents

## Inferred Acceptance Criteria
<!-- 3-8 testable acceptance criteria derived from the change request. Format: AC-N: <criterion>.
     test-strategist uses these to populate the Acceptance Criteria → Test Mapping table. -->
- AC-1:
- AC-2:
- AC-3:

## Tasks Not Applicable
<!-- Comma-separated task IDs from tasks.yml that do NOT apply to this change.
     /cdd-new SKILL marks these as `status: skipped` in tasks.yml.
     Include 1.3 when design.md is not required. -->
- not-applicable:

## Clarifications or Assumptions

## Context Manifest Draft
<!-- Classifier fills this section. In /cdd-new Step 2.3, Claude copies it verbatim into
     specs/changes/<change-id>/context-manifest.md, replacing the scaffold.
     All paths must be repo-relative. Gate enforces Allowed Paths against agent files-read logs. -->

### Affected Surfaces
-

### Allowed Paths
<!-- Union of ALL paths any agent will read. Add change-specific paths below the defaults. -->
- specs/changes/<change-id>/
- specs/context/project-map.md
- specs/context/contracts-index.md

### Agent Work Packets
<!-- One sub-section per required agent (paths must be a subset of Allowed Paths above). -->

#### change-classifier
- specs/changes/<change-id>/
- specs/context/project-map.md
- specs/context/contracts-index.md
