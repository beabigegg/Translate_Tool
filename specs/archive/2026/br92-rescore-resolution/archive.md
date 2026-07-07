# Archive: br92-rescore-resolution

## Change Summary
Retired the phantom business rule **BR-92** ("qe-rescore-threshold") and its env var
**`QE_RESCORE_THRESHOLD`**. Both documented a post-job re-translation behavior (segments
scoring below the threshold get re-translated by a post-translate hook) that **no code
ever implemented** — the constant was parsed in `config.py` but read by nothing, and two
`data-shape-contract.md` rows falsely claimed it was "wired in job_manager.py". This was
pure spec-drift. The user chose RETIRE over building the behavior (the build path would
have been a second COMET-based re-translation gate redundant with the existing LLM-judge
gate). Deletion-only; no runtime behavior changed.

## Final Behavior
No functional change at runtime. Contracts, config, env schema/template, and tests no
longer claim a post-job rescore/re-translation mechanism. The per-segment QE score list
(`score_blocks`) is documented as feeding only the critique adoption gate (BR-89). Setting
`QE_RESCORE_THRESHOLD` in the environment now has no effect anywhere (as before, but now
also undocumented).

## Final Contracts Updated
- `contracts/business/business-rules.md` — BR-92 row deleted (no renumber; intentional gap).
- `contracts/env/env-contract.md` — `QE_RESCORE_THRESHOLD` row deleted; "rescore" clause
  scrubbed from the `QE_ENABLED` row.
- `contracts/env/env.schema.json` — `QE_RESCORE_THRESHOLD` property removed (valid JSON preserved).
- `contracts/env/.env.example.template` — comment + `#QE_RESCORE_THRESHOLD=0.5` sample removed.
- `contracts/data/data-shape-contract.md` — two false "wired" BR-92 claims removed (lines 780, 787).
- `app/backend/config.py` — inert `QE_RESCORE_THRESHOLD` constant removed.
- `docs/adr/0014-retire-phantom-br-and-inert-env-var.md` — NEW ADR recording the repo's
  first formal BR-retirement convention.

## Final Tests Added / Updated
- `tests/test_quality_evaluation.py` — deleted 4 presence/parsing tests; added
  `test_qe_rescore_threshold_not_in_config` + `test_br_92_removed_from_business_rules`.
- `tests/test_env_contract.py` — deleted 4 `TestQeDefault` presence tests; added class
  `TestQeRescoreThresholdRetired` (6 absence tests incl. a live-surface `app/backend` +
  `contracts/` zero-reference sweep that intentionally excludes `tests/`, `specs/`, and
  `.cdd/code-map.yml`). Kept the 2 `QE_ENABLED` default-true regression guards.
- All pass in the `translate-tool` conda env; recorded in `test-evidence.yml` across
  collect / targeted / changed-area / contract phases.

## Final CI/CD Gates
No workflow edits. The existing blanket `pytest tests/ -x -q` step (`contract-and-fast-tests`
job) auto-discovers the deleted/inverted tests, and `cdd-kit validate --contracts` catches a
partial retirement. PR #14 CI: contract-and-fast-tests, full-regression, golden-sample,
libreoffice, renderer-equivalence, text-expansion, expose-output-mode all **pass**.

## Production Reality Findings
- The env var was confirmed inert by a repo-wide grep: only `config.py` referenced it in
  production, and nothing read that reference. Retirement is behavior-neutral.
- The `cdd-kit gate` tier-floor heuristic false-positived on "breaking change / endpoint /
  session" vocab in the plan prose, forcing a `tier-floor-override` despite zero critical
  surface — the documented false-positive class.

## Lessons Promoted to Standards
Both approved by contract-reviewer (learning-promotion validation), applied to the
`CLAUDE.md` `cdd-kit:learnings` managed region:
1. **[promote-to-guidance, NEW]** `CLAUDE.md` cdd-kit:learnings — QE/COMET-dependent tests
   hard-error `ModuleNotFoundError: torch` (do NOT skip) outside the `translate-tool` conda
   env; generate `cdd-kit test run` evidence via `conda run -n translate-tool …` so child
   pytest matches CI (torch pinned in `app/backend/requirements.txt`). Evidence: 8 torch
   failures in base env, 46 pass under conda run; this archive §Production Reality Findings.
2. **[fold-into-existing, net 0 lines]** `CLAUDE.md` cdd-kit:learnings line — extended the
   tier-floor false-positive trigger list with `"breaking change"` and `"session"`
   (`"endpoint"` already present). Evidence: `tasks.yml` frontmatter tier-floor-override.

## Follow-up Work
None. Downstream doc change `qa-mechanism-docs` (#6) depends on this retirement having
landed and will describe the final post-retire QA-pipeline state.

## Cold Data Warning
This archive is historical evidence. Current requirements live in `contracts/` and active
project guidance.
