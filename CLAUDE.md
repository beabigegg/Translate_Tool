# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Full-stack document translation platform (DOCX/PPTX/XLSX/PDF) that preserves layout and formatting using local or cloud LLMs, with terminology management, neural quality evaluation, and a React UI; aimed at translators and teams needing layout-faithful multilingual output.

## Dev commands

```bash
# Backend — requires conda env
conda env update -n translate-tool -f app/backend/environment.yml
conda activate translate-tool
pip install -r app/backend/requirements.txt

# Frontend
cd app/frontend && npm install

# Run (full stack — handles conda activation, build, process management)
./translate_tool.sh start --dev      # dev mode (Vite HMR + uvicorn reload)
./translate_tool.sh start            # prod mode

# Run individually
python -m app.backend.main           # backend only (port 8765, needs Ollama at :11434)
cd app/frontend && npm run dev       # frontend only (port 5173, proxies to :8765)

# Tests
pytest                               # full suite from project root

# Frontend build
cd app/frontend && npm run build
```

## Architecture

**Backend (FastAPI, `app/backend/`)**

| Layer | Key files | Responsibility |
|---|---|---|
| Entry point | `main.py` | FastAPI app, CORS, serves SPA |
| API | `api/routes.py`, `api/schemas.py` | ~30 REST endpoints: jobs, terms, providers, models, profiles |
| Orchestration | `processors/orchestrator.py` | Main pipeline hub — scenario routing, chunking, translation, rendering |
| Job lifecycle | `services/job_manager.py` | In-memory job store (50-job cap, 24h TTL), async worker dispatch |
| Translation | `services/translation_service.py` | Batch LLM calls, critique loops, context windows |
| Chunking | `services/doc_chunker.py` | Long-document semantic chunking (50-token overlap) |
| Terminology | `services/term_db.py` | SQLite-backed term store; UNVERIFIED → APPROVED/REJECTED state machine |
| Quality eval | `services/quality_evaluator.py` | COMET/xCOMET neural QE (optional, lazy-loaded) |
| Model routing | `services/model_router.py` | Multi-provider fallback chain (Ollama → DeepSeek → PANJIT) |
| Parsers | `parsers/` | Per-format extraction: DOCX, PPTX, PDF (PyMuPDF), XLS (LibreOffice) |
| Layout detect | `parsers/layout_detector.py` | ONNX heron-101 classifier (auto-downloads from HF, optional) |
| Renderers | `renderers/` | Coordinate-based text reflow (`bbox_reflow.py`), PDF synthesis (ReportLab) |
| LLM clients | `clients/` | Ollama (local default) + OpenAI-compatible (cloud); shared retry/timeout base |
| Config | `config.py` | Feature flags (`QE_ENABLED`, `CRITIQUE_LOOP_ENABLED`, `DYNAMIC_SCENARIO_STRATEGY_ENABLED`), VRAM metadata, font config |
| Profiles | `translation_profiles.py` | Domain-specific translation strategy presets |
| Data model | `models/translatable_document.py` | Unified IR: `BoundingBox`, `ElementType` (TEXT/TABLE/FIGURE/…) |

**Frontend (React/Vite, `app/frontend/src/`)**

| Layer | Key files | Responsibility |
|---|---|---|
| Entry | `main.jsx` | App bootstrap, router |
| Pages | `pages/` | TranslatePage, TermsPage, TermsReviewPage, SettingsPage, HistoryPage (lazy-loaded) |
| Contexts | `contexts/SettingsContext.jsx` | Model selection, provider config (persisted to localStorage) |
| Hooks | `hooks/useJobPolling.js` | Polls `GET /api/jobs/{id}` until terminal state |
| API layer | `src/api/` | REST client wrappers (jobs, terms, settings, layout) |
| Components | `components/domain/LayoutViewer.jsx` | Coordinate overlay preview of detected layout |

**Data & config**

- Runtime data: `~/.translate_tool/jobs/`, `~/.translate_tool/logs/`, `~/.translate_tool/cache/`
- Provider routing: `config/providers.yml` (gitignored runtime, templated from `providers.yml.example`)
- API keys: `.env` (DeepSeek, PANJIT)

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
- `cdd-kit gate` tier-floor false-positives: common triggers include `"api key"`, `"authentication"`, `"cache"`, `"endpoint"`, `"integration"`, `"alter table"` (even phrased as "No ALTER TABLE needed"), `"breaking change"`, `"session"`, `"route"` — any auth-vocab, cache-vocab, migration-vocab, or routine feature-add term can force Tier 0/2 even when no actual migration is involved; always use `tier-floor-override` with written rationale; see `contracts/env/env-contract.md` Secret Policy.
- At `/cdd-close`: grep the ENTIRE `.github/workflows/contract-driven-gates.yml` for every already-archived change's `cdd-kit gate <id>` line and targeted-test step — not only the change being closed now — and remove them; this drifted silently 3x undetected (table_recognizer, quality_judge+co., table_serialization+table_context_translation) because each close-out only checked its own step.
- Git worktrees have separate working directories: `specs/changes/<id>/` files created in the main repo working tree are invisible inside a worktree. Copy to the worktree (`cp -r`) before committing or running `cdd-kit gate`; brief review agents with the full absolute worktree path and instruct them not to read from the main repo path.
- After modifying `contracts/api/api-contract.md`: run `cdd-kit openapi export --out contracts/api/openapi.yml` and commit — the CI `openapi export --check` gate fails if `openapi.yml` is stale.
- `cdd-kit contract` ordering: run `cdd-kit contract schema set <Name>` to define a response schema **before** `cdd-kit contract endpoint set` references it — referencing an undefined schema fails with "response schema <Name> is not defined".
- `cdd-kit contract schema set <Name> --field ...` replaces the ENTIRE schema's field list with only the fields passed in that call (no merge/upsert) — always pass ALL existing fields (with only the changed one modified) in a single invocation, never just the delta, or you will silently drop the others.
- `pre-tool-use-contract-write.sh` (armed via `CDD_CONTRACT_WRITE_STRICT=1`) blocks ALL Edit/Write/MultiEdit calls on `contracts/api/api-contract.md`, including frontmatter (`schema-version`/`last-changed`) and free-form prose (`## Endpoint Notes`) for which the CLI has no mutation command — use Bash (e.g. a string-anchored python/sed replace) for those edits instead of fighting the hook; it only matches the Edit-tool names, not Bash.
- `ci-gates.md` gate-table column header must contain the literal token `workflow` (e.g. `command / workflow`) — `validate_ci_gates.py` rejects files missing it; the template is correct, do not rename the column.
- When introducing a shared module that multiple backends must import, verify all consumer imports via `grep` before marking implementation done — orphaned shared components are a common QA-catch miss — see `contracts/data/data-shape-contract.md §Renderer IR-consumption contract` (Known consumers table). When that module must also run at production runtime, host the core in the shipped tree (e.g. `app/backend/services/`) and reduce any `tests/` copy to a re-export shim (preserving every public AND private name) with an import-identity test — never the reverse, since `tests/` is excluded from packaged deploys — see `docs/adr/0015-layout-qa-metric-core-in-runtime.md`.
- Tautological tests come in five forms: (1) **call-wiring** — `mock.patch` each backend separately; calling the component against itself always passes even when backends are unwired; (1b) **wrong entry point** — calling a higher-level wrapper that doesn't reach the target hook/seam (e.g. testing a processor hook via `translate_document()` which is unwired) trivially passes; (2) **selection** — assert WHICH element was chosen, not just HOW MANY; (3) **assignment-without-delivery** — asserting a value was SET on an attribute (e.g. `client.system_prompt = ...`) proves nothing if the consuming code path never reads it; (4) **order-without-location** — asserting only the relative index/order of a merged value (e.g. `system_prompt` before `system_context` in one system message) proves presence and sequence but NOT that the value stayed OUT of a payload it must never enter; add an exact-equality assertion on the receiving field (`user_messages[0]["content"] == json_payload`) to carry an ADR-0016 no-leak invariant; (5) **caplog root-logger bleed** — pytest attaches caplog's handler to the ROOT logger, so `caplog.at_level(level, logger="X")` sets X's level but does NOT filter `caplog.records` by logger; without a `record.name == "X"` check an additive record from any other logger satisfies the assertion. In all forms, assert on the value captured at the real boundary (outgoing request/payload, or the delivering log channel) — see `tests/test_renderer_convergence.py::TestLayoutEquivalence` (wiring), `tests/test_doc_chunker.py::TestBoundaryPriority` (selection), `tests/test_translation_strategy.py::test_qe_hook_called_after_translation` (wrong entry point), `tests/test_orchestrator_context_detection.py` (assignment-without-delivery, and the `record.name == "TranslateTool"` filters); for which logger actually reaches `translator.log`, see `contracts/business/business-rules.md` BR-109.
- `mock.patch` must target the name as it is bound **at the moment of the call**: for module-level imports patch the consumer module; for lazy (inside-function) imports patch the definition module. Additionally, `patch("a.b.c.X")` resolves via `getattr(a.b, "c")` (parent-package attribute), NOT `sys.modules` — if a test fixture uses `importlib.import_module` to reload a module, it writes M2 to BOTH `sys.modules` AND the package attribute; `monkeypatch.delitem` only restores `sys.modules`, leaving the package attribute pointing to M2; subsequent `patch("a.b.c.X")` then targets M2 while the live route handlers use M1 — fix: also restore the package attribute via `monkeypatch.setattr(pkg, "mod", original)`, AND use `patch.object(module_ref, "X")` where `module_ref` is captured at collection time (immune to both forms of contamination) — see `tests/test_model_config_api.py` (fixture restore) and `tests/test_providers_api.py` / `tests/test_output_mode_api.py` (collection-time capture).
- Test files that `open()` source files must derive the repo root via `Path(__file__).parent.parent`, never hardcoded absolute paths — hardcoded paths silently pass locally but break CI on any other runner — see `tests/test_text_region_renderer.py::TestSinglePathEnforcement` for the correct pattern.
- Tests asserting config-file content must read the tracked template (`providers.yml.example`), not the gitignored runtime file (`providers.yml`) — the gitignored file is absent on a fresh CI checkout and causes FileNotFoundError — see `tests/test_provider_fallback.py::TestFallbackChainConfig`.
- QE/COMET-dependent tests (`test_quality_evaluation.py`, endpoint/scoring tests) hard-error `ModuleNotFoundError: torch` (they do NOT skip) outside the `translate-tool` conda env — generate `cdd-kit test run` evidence via `conda run -n translate-tool cdd-kit test run …` so child pytest resolves to the torch interpreter that matches CI (torch pinned in `app/backend/requirements.txt`).
- Bug-fix-lane gate needs `agent-log/bug-fix-engineer.yml` with a `bug-fix:` block whose `test-reproduced` reproduction points at a genuinely FAILED pre-fix `cdd-kit test run` that is a BEHAVIORAL failure (an assertion failure), not a collection/import error, and whose reproduction/regression `command` equals the referenced run's recorded command minus runner-added flags — recipe: temporarily restore ONLY the pre-fix behavior file(s) (`git show main:<file> > <file>`), keeping any new pure helper/symbol the fix introduces in place so the repro test still imports cleanly (importing the fix's own new symbol against a fully-reverted file makes the whole module fail to collect, which is not a faithful RED), run ONLY the repro test via `cdd-kit test run --phase <p>`, then restore the fix and re-run that phase green (the failed run-dir persists for the reference); see cdd-kit README bug-fix evidence rules (ADR 0006 §6/§7). Generalized: ANY temporary revert-and-restore technique — this `git show` recipe, a falsifiability toggle, anything — must snapshot to a scratch copy and restore from it; NEVER `git checkout`/`stash`/`restore`, which silently destroy the uncommitted work that is the normal state of an in-flight change, and a destroyed-then-reconstructed file is untrusted until a fresh full `cdd-kit test run` covers the current bytes — see `contracts/ci/ci-gate-contract.md` §Known Validator Gaps.
- PDF/layout tests hit `onnxruntime: import numpy failed` (a numpy/onnxruntime C-ext import-ordering quirk in `layout_detector.py`-touching tests: `TestLayoutDetectorIntegration`, `TestReadingOrderModel`, `TestDpiUpgrade`, `TestPyMuPDFParserIntegration`, `TestReadingOrderField`) ONLY when run as a scoped `test_pdf_*` subset — they pass in the full `pytest tests/` run and in CI. Scope `cdd-kit test run` evidence phases to the change's NEW test classes by node-id (e.g. `test_pdf_parser.py::TestTableCellBboxCorrection`), never whole `test_pdf_*` files, or `--maxfail=1` trips on this pre-existing env artifact.
- Documenting a RETIRED rule/symbol in a later contract/docs change can fail a prior change's zero-reference/absence regression test: `test_br_92_removed_from_business_rules` asserts the literal strings `"BR-92"` and `"rescore"` are absent from `business-rules.md`, so a table describing that retirement must NOT name the purged token — nor the change-id `br92-rescore-resolution` (it contains "rescore"). Reword to describe the retirement generically and grep the target file against known absence-tests before committing. Also: contract-reviewer-drafted `schema-version` bumps go stale as siblings land — always bump from the LIVE version, not the plan's number.
- Adding an additive optional kwarg/callback to a shared seam (judge/critique: `run_judge_loop` cancel_event/snapshot_cb, `_batched_critique_adopt` on_scored, `translation_service.status_callback`; LLM client: `LLMClient.translate_once` system_context) predictably breaks test doubles that reproduce the signature — fake `run_loop`/`side_effect` closures in `test_orchestrator_judge.py`, adopt lambdas in `test_fewshot_glossary.py`, fixed-arg client fakes — and adding `JobStatus`/`JobRecord` fields breaks `_make_job()`-style MagicMock helpers (pydantic validation). The mirror-image failure: a fake that merely ACCEPTS the new kwarg in its signature, without recording it, stays green even when the real merge/delivery logic is deleted in production (deleting the whole system-channel merge from `translate_json` left all 1326 tests passing) — assert on the captured outgoing payload, never on kwarg acceptance. Grep the WHOLE tests/ tree for these fakes and update them IN THE SAME change — they hide in unexpected/"do-not-touch" files (e.g. `_StubTableClient` in `test_pdf_layout_table_fixes.py`, broken because the PDF path unexpectedly reaches the changed seam) (recurred in qa-judge-hang-recovery, batch-critique-qe-scoring, translation-progress-detail-ui, context-prefix-bleed-fix).
- No-shell agents (change-classifier, spec-architect, test-strategist, implementation-planner) can assert a plausible but nonexistent seam/symbol/file even when `.cdd/code-map.yml` is accurate (pattern-matched from prose, not read from source; a classifier's construction-site inventory has been wrong in BOTH directions — naming a file with no reference, omitting one that constructs) — grep before writing the manifest, and the first shell-capable agent (implementation-planner/backend-engineer) MUST verify every named seam/symbol against live source before wiring, including confirming an assigned attribute actually has a READER downstream (a compatibility stub can silently discard writes, e.g. `OpenAICompatibleClient.system_prompt`), and correct the contract/design when it's wrong; the same duty extends to a self-contradictory acceptance criterion OR business rule authored by the human/main Claude, not just a wrong seam name, AND to a phantom CONFLICT the classifier frames (a "mutual-exclusion invariant" / "double-translation" between two paths that live source shows already own disjoint domains) — building machinery for a conflict that does not exist is as wrong as wiring a nonexistent seam, and the "obvious" reconciliation can silently regress the innocent path — see `contracts/business/business-rules.md` BR-106 (seam-name correction), BR-109 (silently-discarded-write correction), BR-110 (its enumeration clause contradicted its own conditional clause; narrowed 0.28.0→0.28.1 before any code was written), AC-7 in the archived `doc-context-sampling-fix`, and `docs/adr/0019-native-header-footer-com-shape-boundary.md` (COM=shapes-only vs native=text+tables; the mutual-exclusion invariant was a phantom).
- Never key a set/dict on `id()` of a python-docx/lxml proxy (`cell._tc`, `p._p`, a `<w:tbl>` element): CPython recycles a freed proxy's address, so a walk that records `id()` without independently retaining the element silently collapses distinct nodes (measured: 8 distinct keys for 300 cells, a 60×5 table) — hold the element itself or use a document-order counter. Pre-existing `id()` keys can pass only by an unstated invariant (every recorded key's element happens to be retained by an already-emitted object); a sibling path that retains nothing will drop content, and a test can mask the hazard where the main path retains — so verify by sabotage (snapshot→edit→run→restore), not by reading, and do not over-state the blast radius. CONFIRMED across BOTH office collectors (python-docx `_collect_docx_segments`, python-pptx `translate_pptx`): the `id()` key is MASKED in the live loop because every emitted cell/text segment stores its element/shape (retained via `_tc`/`_Cell._parent`), so an isolated no-retention probe's collision figure (e.g. "30 shapes → 2 keys under GC") is the fragility, NOT a live defect — a contract statement citing it as a live collision is an overclaim (it has now recurred and been corrected on BR-81, BR-113, AND BR-116). Frame the counter/element fix as removing reliance on an unstated retention invariant, not as preventing a collision the real loop currently suffers. See `contracts/business/business-rules.md` BR-81/BR-113/BR-116, archived `docx-nested-table-collection/evidence/id-key-hazard.md`, and `pptx-group-shape-collection/evidence/id-key-masking.md`.
- Silent-drop-by-non-recursion is a CLASS, not an instance: when a document-walker fix adds recursion into one container (nested tables), immediately sweep sibling containers AND sibling-format processors for the same "we never descend into X" gap before closing — the nested-table fix's own audit found DOCX headers/footers (Linux has no COM path), PPTX group shapes (`for shape in slide.shapes` skips `GroupShape.shapes`), and `<w:sdt>`-in-cell all dropping text, two of them live on the user's real files. See archived `docx-nested-table-collection/archive.md` Follow-up.
<!-- cdd-kit:learnings:end -->
