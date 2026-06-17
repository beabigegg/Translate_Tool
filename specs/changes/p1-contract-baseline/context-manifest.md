# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
-

## Allowed Paths
<!-- UNION of all repo-relative paths (or globs) any agent may read for this change.
     cdd-kit gate validates every agent's files-read log against this list.
     If an agent legitimately read a path, add that path here; do not remove it
     from files-read just to pass gate.
     Be specific — wide globs (e.g. src/) defeat read-scope governance.
     Always include the three defaults below; add change-specific paths beneath them. -->
- specs/changes/<change-id>/
- specs/context/project-map.md
- specs/context/contracts-index.md

## Required Contracts
-

## Required Tests
-

## Agent Work Packets
<!-- One sub-section per required agent. Each path list must be a subset of Allowed Paths above.
     Add or remove sub-sections to match Required Agents in change-classification.md.
     These sub-sections are documentation only — gate enforces Allowed Paths, not individual packets. -->

### change-classifier
- specs/changes/<change-id>/
- specs/context/project-map.md
- specs/context/contracts-index.md

### <implementation-agent>
<!-- Replace with actual agent name, e.g. backend-engineer, frontend-engineer -->
- specs/changes/<change-id>/
- contracts/
- src/
- tests/

### <review-agent>
<!-- Replace with actual agent name, e.g. contract-reviewer, qa-reviewer -->
- specs/changes/<change-id>/
- contracts/

## Context Expansion Requests

<!--
Agents must request context expansion instead of reading outside their work
packet. Format example for real requests:

- request-id: CER-001
  requested_paths:
    - src/example.ts
  reason: why this file is required
  status: pending
-->
-

## Approved Expansions
-
