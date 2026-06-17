# Agents Overview

Use these agents as reusable Claude Code subagents. Project-level agents may be placed in `.claude/agents/`; user-level agents may be placed in `~/.claude/agents/`.

## Core agents

Pick by the job to be done. Each line says when to reach for the agent and, where two agents look similar, how they split.

- `change-classifier`: first stop for any new request — decides change type, tier, and which artifacts and agents are required.
- `repo-context-scanner`: detect the stack, build/test commands, contracts, and CI before planning in an unfamiliar repo.
- `implementation-planner`: turn an approved change into a file-level execution plan; run before any implementation agent.
- `spec-architect`: judge architectural impact and write design/ADRs when a change crosses module boundaries or makes a hard-to-reverse decision.
- `contract-reviewer`: own API/CSS/env/data/business/CI contract consistency; review whenever a contract file changes.
- `dependency-security-reviewer`: vet new or updated dependencies, lockfile changes, license risk (GPL/AGPL), and database migrations.
- `test-strategist`: map acceptance criteria to the test families that must be written before implementation.
- `ci-cd-gatekeeper`: define and enforce required vs nightly/weekly/manual CI gates and the promotion policy.
- `backend-engineer`: implement server/API/data changes under existing contracts and the test plan.
- `frontend-engineer`: implement UI changes under API/CSS/visual contracts and accessibility rules.
- `bug-fix-engineer`: reproduce a reported defect, find root cause, and ship the smallest safe fix with a regression test. Pick over backend/frontend-engineer when the task is a defect, not a feature.
- `qa-reviewer`: run quality gates, verify evidence, and decide release readiness; routes failures back to the owning agent.
- `ui-ux-reviewer`: review interaction, copy, information hierarchy, and empty/error/loading semantics — not pixels or CSS.
- `visual-reviewer`: review pixel layout, responsive behavior, screenshot diffs, and CSS-contract compliance — not interaction or copy.
- `e2e-resilience-engineer`: write real user-journey, failure-injection, and data-boundary tests.
- `stress-soak-engineer`: design load, stress, soak, and long-running stability tests for data-heavy or auto-refreshing features.
- `monkey-test-engineer`: design adversarial, invalid-input, and rapid-action tests, each mapped to a known failure mode.
- `spec-drift-auditor`: audit drift between contracts, code, tests, and CI across multiple iterations.
