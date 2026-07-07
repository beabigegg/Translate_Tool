# Archive: qa-mechanism-docs

## Change Summary
Documentation-only contract change that makes the QA/quality pipeline's three
independent quality mechanisms legible in one place and stops the API/data-shape
surfaces from implying a gating relationship that does not exist. No behavior,
schema, field, type, or nullability change. Depended on #1/#2/#3 landing (all
merged), so its cross-references point at the real live rules. Tier 4, docs lane.

## Final Contracts Updated
- `business-rules.md` — new **Table Y** (QA/quality-pipeline mechanism relationships)
  cross-referencing (not restating): (1) in-line critique loop (BR-89/90, now batched);
  (2) post-job bulk COMET scoring (BR-55/56, permanently dashboard-only); (3)
  LLM-as-judge (BR-72..77 + BR-98/99/100). Records that mechanisms (1) and (3) share
  no state and can disagree by design. Frontmatter 0.24.0 → 0.24.1.
- `api-contract.md` — `quality_score_avg` note gains advisory/non-gating language.
  0.10.0 → 0.10.1; `openapi.yml` re-exported (in sync).
- `data-shape-contract.md` — advisory/non-gating paragraph before `BlockQualityScore`.
  0.17.0 → 0.17.1.
- `contracts/CHANGELOG.md` — three entries.

## Verification
- `cdd-kit validate --contracts`/`--versions` + `openapi export --check` green.
- No test surface (Tier 4; `test-evidence-not-applicable`). PR #19 CI all required gates green.

## Production Reality Findings
- **Retired-symbol vs purge-test collision (caught at CI, fixed):** the first PR CI run
  FAILED `tests/test_quality_evaluation.py::test_br_92_removed_from_business_rules`. The
  br92-rescore-resolution change (#1) added that regression asserting the literal strings
  `"BR-92"` and `"rescore"` are absent from `business-rules.md`. This change's Table Y +
  advisory prose documented the retirement by NAMING BR-92 / the rescore bridge (and even
  named the change-id `br92-rescore-resolution`, which contains "rescore"), reintroducing
  the purged tokens. Fixed by rewording all three edited files to describe the retirement
  WITHOUT the forbidden tokens (e.g. "a previously-proposed post-job score-threshold
  re-translation bridge was retired"); full suite returned to 1164 pass.
- Version bumps were taken from the LIVE contract versions (0.24.0/0.10.0/0.17.0), not the
  plan's stale numbers (0.23.0/0.10.0/0.15.0) — siblings had advanced them since planning.

## Lessons Promoted to Standards
1. **[promote-to-guidance]** `CLAUDE.md` cdd-kit:learnings — when a docs/contract change
   documents a RETIRED rule/symbol, a prior change's zero-reference/absence regression test
   may forbid even naming it; describe the retirement without the purged token and grep the
   target file against prior absence-tests before committing.
- Also worth remembering (not separately promoted): contract-reviewer-drafted version bumps
  go stale as siblings land — always bump from the LIVE `schema-version`, not the plan's number.

## Follow-up Work
`translation-progress-detail-ui` (#7) is the last change — observational UI wired against
the now-final critique (#5) + judge (#2/#3) code.

## Cold Data Warning
This archive is historical evidence. Current requirements live in `contracts/` and active project guidance.
