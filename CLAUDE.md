# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

<TODO: one-sentence description of what this repo does and who uses it>

## Dev commands

<TODO: fill in install / dev / test / lint / build commands for this project>

## Architecture

<TODO: describe main modules, service boundaries, and entry points>

---

This repository follows the Contract-Driven Delivery workflow.

- `contracts/` is the single source of truth for what the system should do.
- `tests/` proves the contracts hold.
- `specs/changes/<id>/` records why decisions were made (passive archive — read only when investigating history).
- To start any non-trivial change, use `/cdd-new <description>` in Claude Code.

## CDD Kit Commands

| command | when to use |
|---|---|
| `/cdd-new <description>` | start a new tracked change (scaffolds all artifacts, runs full agent flow) |
| `/cdd-resume <id>` | continue an in-progress change after a session break |
| `/cdd-close <id>` | close a completed change: promote learnings, archive |
| `cdd-kit list` | show all active changes and their status |
| `cdd-kit gate <id>` | verify a change is gate-ready (run before PR) |
| `cdd-kit gate <id> --strict` | full gate with pending-task enforcement (pre-commit default) |
| `cdd-kit context check <id> --path <paths...>` | preflight expected agent reads against `context-manifest.md` before invoking the agent |
| `cdd-kit archive <id>` | physically move a completed change to `specs/archive/<year>/` |
| `cdd-kit abandon <id> --reason <text>` | mark a change as abandoned; preserves directory for git history |
| `cdd-kit migrate <id> \| --all` | upgrade pre-v1.11 change directories to new format (frontmatter + tier format) |
| `cdd-kit validate` | run all contract validators |
| `cdd-kit detect-stack` | detect the project tech stack |

Run `cdd-kit detect-stack` to verify the detected tech stack.

## Recommended MCP Tools

Configure MCP-capable agents to use the cdd-kit server:

```bash
claude mcp add --scope user cdd-kit -- cdd-kit mcp
claude mcp list
```

For Claude Code, use `claude mcp add` so the server is written to
`~/.claude.json`. Do not rely on manually adding `mcpServers` to
`~/.claude/settings.json`; that is a Claude Code UI settings format and is not
the MCP registry read by the CLI.

Prefer these MCP tools before reading source files: `cdd_graph_context`,
`cdd_graph_query`, `cdd_graph_impact`, `cdd_index_query`, and
`cdd_index_impact`. They use `.cdd/code-map.yml` and
`.cdd/code-graph.index.json` as the project exploration layer. If MCP is not
available, use the equivalent CLI commands: `cdd-kit graph ...` and
`cdd-kit index ...`.

Pass `withSource: true` (MCP) or `--with-source` (CLI) on `query` to get the
matched symbol's code inline. The query then replaces a follow-up `Read` instead
of preceding it — use a plain `Read` only for ranges the query did not return
(e.g. a range flagged as source-budget truncated).

## API Conformance

If `.cdd/conformance.json` has `"enabled": true`, `cdd-kit validate --contracts`
(and `cdd-kit gate`) mechanically check real backend routes and frontend call
sites against `contracts/api/api-contract.md`. Do not add, rename, or call an
endpoint without updating the contract in the same change, or the gate will fail
on the drift. See `docs/api-conformance.md`.

## Context Governance

For context-governed changes, read `specs/changes/<change-id>/context-manifest.md` before using file-reading or broad search tools.

- Read only paths allowed by the manifest or approved expansions.
- Before invoking an agent with known concrete reads, run
  `cdd-kit context check <change-id> --path <paths...>`. If it fails and the
  reads are legitimate, expand `Allowed Paths` or approve a Context Expansion
  Request before the agent reads the files.
- If more context is needed, stop and write a Context Expansion Request in the manifest (`cdd-kit context request`).
- Optional agent-log notes are defined in
  `~/.claude/skills/contract-driven-delivery/references/agent-log-protocol.md`.
  Read that once; do not paraphrase it elsewhere.

## CDD Operational Notes

- After each agent returns, tick the related `tasks.yml` items immediately,
  and only then move to the next agent.
- Do not start backend/frontend/test implementation agents until
  `implementation-plan.md` is ready; implementation agents should follow that
  plan and report `blocked` instead of inferring missing scope from chat
  history.
- Pre-existing test failures may be excluded from the current gate only when
  `qa-report.md` records the failing test, baseline evidence, why it is outside
  scope, owner, and follow-up.

### Promoted Learnings

This file is loaded into every session, so size here is a recurring token cost.
`/cdd-close` consolidates promoted lessons **inside the markers below only**.
Each entry is **one terse line: a rule + a pointer to where the detail lives**
(`contracts/…` for product/behavior, `docs/…` for workflow detail) — never an
inline playbook. New lessons **merge into or replace** an existing entry instead
of appending; obsolete or contract-superseded entries are removed. Anything you
write **outside** the markers is yours and is never edited or evicted.

<!-- cdd-kit:learnings:start -->
- MySQL ENUM contraction / any `ALGORITHM=COPY` DDL = high risk on large tables (row-count + online-migration/maintenance-window + rollback required) — see `contracts/data/` migration rules.
- `cdd-kit gate` validates all contracts globally — pre-existing empty stubs outside your change scope will block the gate; ensure all contracts have minimal real content before gate run.
- `cdd-kit gate` tier-floor false-positives: common triggers include `"api key"`, `"authentication"`, `"cache"`, `"endpoint"`, `"integration"`, `"alter table"` (even phrased as "No ALTER TABLE needed") — any auth-vocab, cache-vocab, migration-vocab, or routine feature-add term can force Tier 0/2 even when no actual migration is involved; always use `tier-floor-override` with written rationale; see `contracts/env/env-contract.md` Secret Policy.
- At `/cdd-close`: remove the archived change's `cdd-kit gate <id>` line from `.github/workflows/contract-driven-gates.yml` — archived dirs no longer exist under `specs/changes/` and CI fails with "change not found".
- After modifying `contracts/api/api-contract.md`: run `cdd-kit openapi export --out contracts/api/openapi.yml` and commit — the CI `openapi export --check` gate fails if `openapi.yml` is stale.
- `cdd-kit contract` ordering: run `cdd-kit contract schema set <Name>` to define a response schema **before** `cdd-kit contract endpoint set` references it — referencing an undefined schema fails with "response schema <Name> is not defined".
- `ci-gates.md` gate-table column header must contain the literal token `workflow` (e.g. `command / workflow`) — `validate_ci_gates.py` rejects files missing it; the template is correct, do not rename the column.
- When introducing a shared module that multiple backends must import, verify all consumer imports via `grep` before marking implementation done — orphaned shared components are a common QA-catch miss — see `contracts/data/data-shape-contract.md §Renderer IR-consumption contract` (Known consumers table).
- When testing multi-backend shared-component wiring, use `mock.patch` to assert each backend calls the shared function — calling the component twice against itself is tautological and always passes even when backends are unwired — see `tests/test_renderer_convergence.py::TestLayoutEquivalence` for the correct mock-based pattern.
- Test files that `open()` source files must derive the repo root via `Path(__file__).parent.parent`, never hardcoded absolute paths — hardcoded paths silently pass locally but break CI on any other runner — see `tests/test_text_region_renderer.py::TestSinglePathEnforcement` for the correct pattern.
<!-- cdd-kit:learnings:end -->
