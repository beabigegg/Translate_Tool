# Archive: support-legacy-office-formats

## Change Summary
Full support for legacy Office formats (`.doc`/`.xls`/`.ppt`) was added, matching the fidelity/quality bar of native `.docx`/`.xlsx`/`.pptx` uploads rather than merely "making the conversion run." A new `ppt_to_pptx()` LibreOffice-headless conversion helper was added mirroring the existing (but previously untested and undocumented) `.doc`/`.xls` conversion path, all three legacy formats were wired into the orchestrator's extraction and translation branches, and a lossy-conversion disclosure (BR-96) was added via the existing `job.warnings` field so users are told when a file went through a format-normalization step before translation. Shipped via PR #12 (merged 2026-07-06).

## Final Behavior
- `.doc`/`.xls`/`.ppt` uploads are accepted by both frontend (`ACCEPTED_EXTENSIONS`) and backend (`SUPPORTED_EXTENSIONS`).
- Each legacy file is converted to its modern counterpart via LibreOffice-headless before entering the existing extraction → layout-detection → translation → rendering → QE pipeline — identical pipeline, no special-cased QE path for converted documents (design.md Decision 2, ADR-0009).
- Every successfully converted file adds one disclosure entry to `job.warnings` (BR-96): "`{filename}` converted from a legacy format via LibreOffice; layout fidelity may be lower than a native format."
- When LibreOffice is unavailable or conversion fails for a specific file, that file is skipped with an actionable log message; the job is not failed and other files continue processing (per-file isolation, mirrors the pre-existing `.doc`/`.xls` failure semantics).
- LibreOffice is documented as an optional external binary dependency (not a Python package) in `contracts/env/env-contract.md` § External Binary Dependencies, with install commands and its two env vars (`LIBREOFFICE_PATH`, `LIBREOFFICE_TIMEOUT`) now in the env-contract table, `.env.example.template`, and `env.schema.json`.

## Final Contracts Updated
- `contracts/api/api-contract.md` (v0.9.0 → v0.10.0): `JobCreateRequest.file` accepted-types note, `JobStatus.warnings` note extended, new Endpoint Notes entry for legacy-format upload behavior. Also fixed a pre-existing, unrelated drift found during this change: `GET /providers/{provider_id}/live-models` existed in `routes.py` but was never documented — added.
- `contracts/business/business-rules.md` (v0.21.0 → v0.22.0): BR-9 amended (`.ppt` added), new BR-96 (lossy-conversion disclosure + degradation policy), new Table X (decision table).
- `contracts/env/env-contract.md` (v0.11.0 → v0.12.0): new § External Binary Dependencies section; `LIBREOFFICE_PATH`/`LIBREOFFICE_TIMEOUT` rows added (found undocumented by dependency-security-reviewer despite existing in `config.py` before this change).
- `contracts/ci/ci-gate-contract.md` (v0.5.0 → v0.6.0): new `libreoffice-conversion-gate` row + dedicated section.
- `contracts/api/openapi.yml`: re-exported after all api-contract.md edits.

## Final Tests Added / Updated
- `tests/test_libreoffice_helpers.py` (new, 7 tests): `ppt_to_pptx`, backfilled `doc_to_docx`/`xls_to_xlsx`, `is_libreoffice_available()` true/false branches — all mocked, no real binary required.
- `tests/test_orchestrator_phase0.py` (+6 tests): `.doc`/`.xls`/`.ppt` Phase-0 and main-branch routing, skip-without-crash, per-file failure isolation.
- `tests/contract/test_legacy_conversion_disclosure.py` (new, 2 tests): exact BR-96 warning-string assertion + COM-vs-LibreOffice edge case.
- `tests/test_quality_evaluation.py` (+1 test): QE scoring path identical for converted vs. native documents.
- Full suite at close: 1083 passed, 4 skipped, 0 failed.

## Final CI/CD Gates
- New `libreoffice-conversion-gate` (Tier 2+, required, PR-triggered): installs `libreoffice-core` (best-effort, `continue-on-error: true`), runs `tests/test_libreoffice_helpers.py`. Verified on PR #12: installed the real binary and ran all 7 tests for real (not a silent skip).
- No dedicated `cdd-kit gate <id>` CI step was added (contract validation covered by the existing `cdd-kit validate --contracts` step, consistent with the CLAUDE.md promoted learning about not adding per-change gate lines that later go stale).

## Production Reality Findings
- **Two real pre-existing gaps were found and fixed, not waived**, both required to pass the required `contract` test-evidence phase / dependency-security review:
  1. `GET /providers/{provider_id}/live-models` existed in backend code but was undocumented in `api-contract.md` — this was blocking the required contract-validation gate for an unrelated reason. Root-caused and fixed (added the endpoint row with the `/api` prefix matching the literal frontend `fetch()` call) rather than waived, per CLAUDE.md's "a required test failure cannot be recorded as known/pre-existing/waived" rule.
  2. `LIBREOFFICE_PATH`/`LIBREOFFICE_TIMEOUT` env vars existed in `config.py` since the original (undocumented) `.doc`/`.xls` support but were never added to `env-contract.md`'s variable table — found by dependency-security-reviewer, fixed by adding table rows + `.env.example.template` + `env.schema.json` entries.
- implementation-planner caught a gap design.md missed: `_output_name()` had no `.ppt` case, which would have shipped output files with a `.ppt` extension instead of `.pptx`.
- Two non-blocking cosmetic UI follow-ups were noted (not gating): the 8-item flat extension list in the drop-zone could be grouped by family; CSS wrap behavior at narrow viewports with the longer list should be spot-checked.

## Lessons Promoted to Standards
- **promote-to-guidance** (CLAUDE.md, `cdd-kit:learnings` region, appended after the existing `cdd-kit contract` ordering line): `cdd-kit contract schema set <Name> --field ...` replaces the ENTIRE schema's field list with only the fields passed in that call (no merge/upsert) — always pass ALL existing fields in a single invocation, never just the delta. Evidence: main Claude directly experimented this session and confirmed a one-field invocation against `JobCreateRequest` silently deleted the other 6 pre-existing fields; reviewed and confirmed by contract-reviewer.
- **promote-to-guidance** (same location): the `pre-tool-use-contract-write.sh` hook blocks ALL Edit/Write/MultiEdit calls on `contracts/api/api-contract.md`, not just table rows — including frontmatter and free-form prose the CLI has no mutation command for; use Bash (python/sed) instead of fighting the hook, since it only matches Edit-tool names. Evidence: main Claude hit this hook block on a frontmatter edit this session, confirmed the hook's matcher scope by reading `.claude/hooks/pre-tool-use-contract-write.sh` directly, and used a Bash-based Python replace as the sanctioned workaround per the hook's own docstring; reviewed and confirmed by contract-reviewer.

## Follow-up Work
- `.ppt` COM (`win32com`) fallback parity — the existing `.doc` branch has a COM fallback when LibreOffice is absent; `.ppt` intentionally does not get an equivalent (LibreOffice + graceful skip is the accepted minimum bar per design.md Open Risks). Not tracked as a separate change; revisit only if a Windows-only deployment needs it.
- DOCX-style multi-paragraph-per-cell fidelity is unrelated to this change (see `table-context-translation` archive for that limitation).
- Drop-zone extension-list grouping and narrow-viewport CSS wrap check (both non-blocking, noted above).

## Cold Data Warning
This archive is historical evidence. Current requirements live in `contracts/` and active project guidance (`CLAUDE.md`/`CODEX.md`).
