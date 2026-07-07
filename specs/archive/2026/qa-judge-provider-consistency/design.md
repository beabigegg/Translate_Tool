# Design: qa-judge-provider-consistency

## Summary
Today the judge/QA re-translation callback (`_translate_fn`,
`job_manager.py:493-510`) reuses `last_client` — whichever provider won the main
translation phase via `model_router.py`'s fallback chain — with a silent fallback
to `OllamaClient(DEFAULT_MODEL)`. This change makes QA re-translation route
explicitly through the judge's own provider (`JUDGE_CLOUD_PROVIDER_ID`, default
`panjit`), the same provider that scored the block as needing re-translation,
decoupling it from the unrelated main-translation routing decision. The fix is
purely *inside* an already-running judge pass: **BR-97's gate — which skips the
entire judge pass (scoring AND re-translation) when `winning_provider ==
"deepseek"` — is untouched.** We change only *which client executes* the
re-translation call, not *whether the judge pass runs*. All client-construction
logic stays in `quality_judge.py` (matching where `_build_cloud_client()` already
lives, per D4); `job_manager.py` becomes a pure consumer.

## Affected Components
| component | file path(s) | nature of change |
|---|---|---|
| Judge service | `app/backend/services/quality_judge.py` | Add a `translation_client` property (built once, same provider as scoring); generalize `_build_cloud_client()` to accept a per-call `model=` override |
| Judge call site | `app/backend/services/job_manager.py` (493-510) | `_translate_fn` calls `_judge.translation_client.translate_once(...)` instead of `last_client`; drop the `last_client`/`OllamaClient(DEFAULT_MODEL)` fallback |
| Business contract | `contracts/business/business-rules.md` | Add BR-98 + one Table U row (contract-reviewer owns) |
| Env contract | `contracts/env/env-contract.md` | Review-only; add BR-98 cross-ref to existing `JUDGE_*` rows; no new var |

## Key Decisions

- **Decision 1 — build a distinct translation-role client on the judge's
  provider, not reuse the scoring client instance.** `config/providers.yml` (and
  `.example`) show each provider entry carries a `models:` *map* of named roles
  (`panjit` → `translate: gpt-oss:120b`, `long_doc: ...`), and
  `_build_cloud_client()` already passes an explicit `model=` per call. So a
  provider is **not** tied to one model. The re-translation client is built on the
  **same** provider (`JUDGE_CLOUD_PROVIDER_ID`) but selects the provider's
  `models.translate` model (falling back to `JUDGE_MODEL` if that key is absent).
  → *Rejected: reuse the exact `self._client`/`JUDGE_MODEL` scoring instance.*
  Re-translation is a translation task, not a scoring task; overloading a
  judge-tuned model (e.g. a future dedicated judge model) with translation is a
  semantic mismatch. More importantly it would silently *change the model* used
  today: the current `last_client` (winning panjit client) already runs
  `models.translate` (`gpt-oss:120b`); resolving to `models.translate` keeps the
  already-panjit case a true request-for-request no-op (AC-2), whereas reusing
  `JUDGE_MODEL` would diverge whenever operators set a judge model ≠
  `gpt-oss:120b`.
- **Decision 2 — no new config surface.** The translation-role model comes from
  the existing `providers.yml` `models.translate` entry; the provider comes from
  the existing `JUDGE_CLOUD_PROVIDER_ID`. → *Rejected: a new
  `JUDGE_TRANSLATION_MODEL` env var* — the change-request non-goal forbids
  inventing a new config surface, and `models.translate` already expresses this.
- **Decision 3 — client construction lives in ONE place (`quality_judge.py`).**
  Expose `translation_client` on `QualityJudge`; `job_manager.py` consumes it.
  For `JUDGE_PROVIDER="ollama"`, `translation_client` is the local
  `OllamaClient(model=JUDGE_MODEL)` — same (local) provider as scoring, preserving
  provider-consistency symmetrically. → *Rejected: build the client inline in
  `_translate_fn`* — that duplicates provider-resolution logic in `job_manager.py`
  and drifts from the D4 / `_build_cloud_client()` precedent.
- **Decision 4 — BR-98 wording (final text; contract-reviewer did numbering /
  precedent).** Append after BR-97 in the Rule Inventory:
  > **BR-98 | judge-retranslation-provider-consistency** | application-team |
  > When the judge pass runs (i.e. not skipped by BR-97), the QA re-translation
  > callback passed to `run_judge_loop` MUST execute against the judge's own
  > provider — `JUDGE_CLOUD_PROVIDER_ID` when `JUDGE_PROVIDER="cloud"`, else the
  > local Ollama judge client — NEVER `last_client` / `model_router`'s
  > main-translation winner (extends D4, BR-95). Re-translation MAY use a
  > different model within that provider (the provider's `models.translate` role,
  > falling back to `JUDGE_MODEL`) but MUST NOT diverge in *provider*. The prior
  > `last_client is None → OllamaClient(DEFAULT_MODEL)` fallback is removed. When
  > `last_client` already resolved to `JUDGE_CLOUD_PROVIDER_ID`'s provider the
  > behavior is a no-op. | tests/test_orchestrator_judge.py |
  Also add **one Table U row** ("Judge pass runs, re-translation invoked | client
  resolves to `JUDGE_CLOUD_PROVIDER_ID` provider, independent of `last_client`
  (BR-98)"). Rationale for including the row: Table U is the behavioral decision
  table for the judge loop and every sibling rule (BR-72..BR-77) has a row; a
  provider-routing behavior that reviewers must be able to check belongs there for
  parity. → *Rejected: BR-98 inventory entry only, no Table U row* — defensible
  but would make BR-98 the lone judge-loop rule without a decision-table row.

## Migration / Rollback
No data migration, no schema change, no new env var, no API change. The edit is
two backend files plus the contract. Rollback is a straight revert of both source
files and the BR-98 addition; because the already-panjit deployment case is a
behavioral no-op, revert carries no data or output-format risk. No ADR required:
this extends the existing D4 / ADR-0007 / ADR-0008 "judge owns its own client,
never `model_router`" boundary rather than moving a boundary, and the trade-off
is captured in BR-98.

## Open Risks
- If an operator sets `JUDGE_CLOUD_PROVIDER_ID` to a provider whose entry lacks a
  `models.translate` key, the fallback-to-`JUDGE_MODEL` behavior must be tested;
  implementation-planner should make that fallback explicit and covered.
- `qa-judge-hang-recovery` (sibling) also edits this call-site region and depends
  on this change landing first — sequence to avoid a merge conflict in
  `_translate_fn`.
