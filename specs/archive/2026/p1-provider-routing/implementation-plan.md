---
change-id: p1-provider-routing
schema-version: 0.1.0
last-changed: 2026-06-17
---

# Implementation Plan: p1-provider-routing

## Objective

Make per-target-language model routing config-driven from `config/providers.yml`
`routing.rules`, and make `resolve_route_groups()` resolve each `target_lang`
independently (not by `targets[0]`). Concretely, deliver:

1. `model_router.py` reads `routing.rules` from `provider_config` (when present),
   matching each `target_lang` against the rules first and falling back to
   `routing.default` (BR-18, BR-19). The legacy `_OLLAMA_ROUTING_TABLE` path
   (when `provider_config` is `None`) stays byte-for-byte behaviorally unchanged.
2. `resolve_route_groups()` produces one `RouteGroup` per distinct
   `(model, profile_id, model_type, provider)` tuple across the batch — 1..N
   groups for a mixed batch (BR-18).
3. `config/providers.yml` and `config/providers.yml.example` gain a
   `routing.rules` block covering the four languages currently in
   `_OLLAMA_ROUTING_TABLE`: Vietnamese, German, Japanese, Korean.

The implementation is TDD: new failing tests in `tests/test_model_router.py`
land first (red), then `model_router.py` and the config files change to make them
pass (green), with all pre-existing tests still passing unchanged in intent.

## Execution Scope

### In Scope
- `tests/test_model_router.py` — add the new test classes named in
  `test-plan.md` (red phase first).
- `app/backend/services/model_router.py` — add `routing.rules` consumption to
  `_resolve_from_config()`; make `resolve_route_groups()` resolve each target
  independently and group by the full routing tuple.
- `config/providers.yml` — add `routing.rules` block (vi/de/ja/ko).
- `config/providers.yml.example` — mirror the same `routing.rules` block
  (secret-free).
- `contracts/business/business-rules.md` — already updated (BR-4, BR-18, BR-19,
  Table D present). Backend-engineer must NOT change contract prose; only confirm
  the implementation matches BR-18/BR-19/Table D. If a mismatch is found, report
  `blocked` and route to `contract-reviewer` (see Known Risks re: `routing.rules`
  shape).

### Out of Scope
- Any new LLM client, provider type, or transport (no new clients).
- Any new fallback / retry / offline-detection logic (`fallback_chain` semantics
  are owned by the archived `p1-cloud-providers` change; do not touch them).
- Any new or changed API endpoint or request/response schema.
- `get_route_info()` per-language behavior change (test-plan.md §Out of Scope:
  unchanged; it already resolves per-target via `_resolve_from_config`).
- `routing.rules` schema validation / enforcement (test-plan.md §Out of Scope).
- Touching `orchestrator.py` or `translation_service.py` — confirmed NOT callers
  of `resolve_route_groups()` (see Consumer Compatibility).
- Cloud auth, live Ollama/cloud HTTP, or E2E pipeline.
- Opportunistic refactor of `resolve_route`, `get_route_info`, or the Ollama
  legacy grouping branch beyond what AC-3/AC-4 require.

## Required Changes

| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | tests | Add `TestProviderRoutingRules`, `TestResolveRouteGroupsPerLanguage`, `TestLegacyOllamaPath` to `tests/test_model_router.py` per test-plan.md §"New Test Classes" using the `tmp_path` fixture shape; confirm `TestConfigDrivenRouting::test_hardcoded_routing_table_removed` asserts `_OLLAMA_ROUTING_TABLE` absence. Run red phase. | backend-engineer |
| IP-2 | backend | In `model_router.py` `_resolve_from_config()`, read `routing.rules` for the given `target` before falling back to `routing.default` (BR-18, BR-19). | backend-engineer |
| IP-3 | backend | In `model_router.py` `resolve_route_groups()` cloud branch, resolve each target via `_resolve_from_config(target, ...)` and group by the full `(model, profile_id, model_type, provider)` tuple, preserving first-seen order (BR-18). | backend-engineer |
| IP-4 | config | Add `routing.rules` (vi/de/ja/ko) to `config/providers.yml` and mirror in `config/providers.yml.example` (BR-4, AC-2). | backend-engineer |
| IP-5 | verify | Run the test ladder (collect → targeted → changed-area → contract), produce `test-evidence.yml` via `cdd-kit test run`; confirm no pre-existing test regressed. | backend-engineer |
| IP-6 | contract | Verify implementation matches BR-18/BR-19/Table D; do not edit contract prose. Mismatch → `blocked` → contract-reviewer. | backend-engineer |

## Source Artifact Pointers

| source | relevant pointer | used for |
|---|---|---|
| test-plan.md | "Acceptance Criteria → Test Mapping" table | AC → exact test node ids to write |
| test-plan.md | "New Test Classes and Functions Required" | names/intent of the three new test classes |
| test-plan.md | "Fixture Shape Required" | authoritative `routing.rules` YAML shape for tests + IP-4 |
| test-plan.md | "Test Update Contract" | which existing tests may shift group count, which must stay |
| test-plan.md | "Out of Scope" | get_route_info / schema-validation exclusions |
| ci-gates.md | "Required Gates for This Change" table | verification commands (`pytest tests/test_model_router.py`, full suite) |
| contracts/business/business-rules.md | BR-4, BR-18, BR-19 | routing behavior the code must satisfy |
| contracts/business/business-rules.md | Table D | per-language routing decision table |
| docs/adr/0001-config-driven-provider-registry.md | Decision bullet 5 ("THIS change consumes only routing.default…") | confirms `routing.rules` is THIS change's to consume; do not reverse config-driven routing |
| change-classification.md | "Inferred Acceptance Criteria" AC-1..AC-7 | scope of behavior |

## File-Level Plan

| path or glob | action | notes |
|---|---|---|
| `tests/test_model_router.py` | edit (add classes) | Add the 3 new test classes (IP-1). Imports of `RouteGroup`, `resolve_route_groups`, `resolve_route`, `get_route_info`, `DEFAULT_MODEL`, `HYMT_DEFAULT_MODEL` already exist at lines 7-16. Build `routing.rules` fixtures via `tmp_path`; never read real `config/providers.yml`. Pass `provider_config=<parsed dict>` directly to the functions (the functions accept a dict, not a path). |
| `app/backend/services/model_router.py` | edit | IP-2: modify `_resolve_from_config()` (lines 77-101). IP-3: modify `resolve_route_groups()` cloud branch (lines 162-176). Leave the legacy Ollama branch (lines 178-200), `resolve_route` (104-138), and `get_route_info` (203-233) behaviorally unchanged. Update the module docstring (lines 8-9) which currently says `routing.rules` is "schema-tolerated but NOT consumed". |
| `config/providers.yml` | edit | IP-4: add `routing.rules` under existing `routing:` (currently only `routing.default` at lines 28-32). |
| `config/providers.yml.example` | edit | IP-4: mirror the same `routing.rules` block (lines 31-35 currently hold only `routing.default`). Secret-free — no `${VAR}` keys needed in rules (models/providers are literals). |
| `contracts/business/business-rules.md` | read-only | Already contains BR-4/BR-18/BR-19/Table D. Do not edit (IP-6). |

### IP-2 detail — `_resolve_from_config(target, provider_config)`

Current body (lines 86-101) ignores `target` and always returns `routing.default`.
Change to: look up `routing.rules` for `target` first; on a hit, return that rule's
`(model, provider, profile, model_type)`; on a miss (or no `rules` key), fall back
to the existing `routing.default` logic unchanged.

Resolution order inside the function:
1. `rules = routing.get("rules")` — may be absent/`None`/empty → skip to default.
2. If `rules` is present, look up `target` (see schema below). On hit, take
   `model`, `provider`, and `profile` (default `profile` to `"general"` if the
   rule omits it). Derive `model_type` with the SAME logic the default branch
   already uses (currently hardcodes `"general"` for cloud; keep that derivation
   identical so cloud rules behave like the default for `model_type`).
3. On miss, fall through to the existing `routing.default` resolution
   (lines 87-101) verbatim — this satisfies BR-19 (deterministic, no exception).

Do not raise on a missing target, a missing `rules` key, or a malformed rule
entry that lacks `model`/`provider` — degrade to `routing.default`. Schema
validation is explicitly out of scope.

### IP-3 detail — `resolve_route_groups()` cloud branch

Current cloud branch (lines 162-176) calls `_resolve_from_config(targets[0], ...)`
once and wraps ALL targets in a single group. Replace with per-target resolution
that mirrors the legacy Ollama grouping structure (lines 178-200) but using
`_resolve_from_config`:

- Iterate `targets` in order.
- For each, call `_resolve_from_config(target, provider_config)` →
  `(model, profile_id, model_type, provider_id)`.
- Group key = the full tuple `(model, profile_id, model_type, provider_id)`.
- First time a key is seen, create a `RouteGroup` with empty `targets`,
  `refine_model=None` (cloud groups do not use cross-model refinement — preserve
  current cloud behavior; do NOT add the Ollama refine_model logic to the cloud
  branch), and `provider=provider_id`.
- Append `target` to that group's `targets`.
- Return `list(<dict>.values())` preserving first-seen order.

Result: a mixed batch where vi/de/ja/ko map to distinct models yields up to 4
groups; targets sharing a tuple collapse into one group (BR-18, AC-3, AC-4).

## Consumer Compatibility (CER-001 finding)

CER-001 requested read access to `app/backend/processors/orchestrator.py` and
`app/backend/services/translation_service.py` to check single-group assumptions.
Finding: **neither file imports or calls `resolve_route_groups()` or `RouteGroup`**
(verified by grep). The actual consumers of the multi-group return value are:

- `app/backend/api/routes.py:129` — `create_job` calls `resolve_route_groups(...)`.
  It already handles `None` (manual override → single explicit group) and a list
  of N groups. It only reads `route_groups[0].model_type` as a *reference*
  `model_type` for `num_ctx` VRAM bounds (line 144) — using the first group's
  type as the representative is pre-existing behavior and is unaffected by group
  count. **No single-group assumption; no change needed.**
- `app/backend/services/job_manager.py:221` — `create_job(route_groups: List[RouteGroup])`
  already iterates `for group in route_groups` (line 279), computes
  `multi_group = len(route_groups) > 1` (line 273), and tags output filenames per
  target when `multi_group` (line 287). **Already multi-group safe; no change
  needed.**

Conclusion: emitting 1..N groups from the cloud branch is already supported by
both real consumers. Backend-engineer must NOT modify `routes.py` or
`job_manager.py`; they are outside the file-level plan. The one behavior to be
aware of: a mixed cloud batch that previously produced exactly 1 group may now
produce several, which (correctly, per BR-18) triggers `job_manager`'s
per-language output-suffix filenames — this is the intended new behavior, not a
regression.

## `config/providers.yml` routing.rules schema (authoritative: test-plan.md Fixture Shape)

`routing.rules` is a **mapping keyed by target-language name**; each value is an
object with `model`, `provider`, and optional `profile` (defaults to `general`):

```yaml
routing:
  default:
    model: gpt-oss:120b
    provider: panjit
    profile: general
  rules:
    Vietnamese:
      model: <vi-model>
      provider: <vi-provider>
      profile: general        # optional; omit → general
    German:
      model: <de-model>
      provider: <de-provider>
    Japanese:
      model: <ja-model>
      provider: <ja-provider>
    Korean:
      model: <ko-model>
      provider: <ko-provider>
```

Lookup is by exact `target_lang` string (same language names the codebase already
uses: "Vietnamese", "German", "Japanese", "Korean"). For the real
`config/providers.yml` / `.example`, choose `model`/`provider` values consistent
with the registry already defined in those files (the `panjit` / `ollama-local`
providers and their declared models). The four rules must cover the same four
languages the legacy `_OLLAMA_ROUTING_TABLE` covered so no language silently loses
its mapping (change-classification.md Risk Factors). Tests do NOT read the real
file — they build their own `tmp_path` fixtures — so the real-file model choices
are a config decision, not a test dependency.

NOTE on shape discrepancy: BR-4 prose describes rules as "a list of
`{lang, model, provider, profile}` entries", while test-plan.md Fixture Shape uses
a language-keyed map. Tests are the executable spec, so implement the **map-keyed**
shape. Flag the prose/shape mismatch to `contract-reviewer` (see Known Risks); do
not edit BR-4 yourself.

## Contract Updates

- API: none.
- CSS/UI: none.
- Env: none.
- Data shape: none.
- Business logic: BR-4, BR-18, BR-19, and Table D in
  `contracts/business/business-rules.md` are already present and describe the
  target behavior. No new contract edits in this change beyond confirming the
  implementation conforms (IP-6). `business-rules.md` schema-version must read
  `0.3.0` per ci-gates.md Promotion Policy item 3 — verify, do not bump
  arbitrarily.
- CI/CD: ci-gates.md specifies one workflow edit (add
  `cdd-kit gate p1-provider-routing` to `.github/workflows/contract-driven-gates.yml`).
  That edit is owned by the CI/workflow step in ci-gates.md, NOT by the
  backend-engineer in this plan — it is outside the file-level plan. Do not edit
  workflow files here.

## Test Execution Plan

Run via `cdd-kit test run` to produce `test-evidence.yml`; the gate validates the
evidence. Required phases for this change (floor): collect, targeted,
changed-area, plus contract (Tier-1 contract gate is required per ci-gates.md).

Ladder:
1. `cdd-kit test select p1-provider-routing --json` — confirm selection resolves
   to `tests/test_model_router.py` targets.
2. collect — `pytest tests/test_model_router.py --collect-only -q` (new test
   classes are discovered; red phase — new tests fail before IP-2/IP-3/IP-4).
3. targeted — run the specific new node ids below.
4. changed-area — `pytest tests/test_model_router.py -x -q` plus
   `tests/test_hy_mt_quality_refinement.py` (it also imports
   `resolve_route_groups` and exercises the legacy Ollama refine_model grouping —
   it must stay green, proving the legacy path is untouched).
5. contract — `cdd-kit validate --contracts` (asserts business-rules contract
   validates; exit 0).
6. full (required Tier-1 gate, ci-gates.md) — `pytest tests/ -x -q`.

| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1 | tests/test_model_router.py::TestConfigDrivenRouting::test_hardcoded_routing_table_removed | `_OLLAMA_ROUTING_TABLE` no longer the routing source; assertion passes |
| AC-1 | tests/test_model_router.py::TestProviderRoutingRules::test_routing_rules_key_consumed_from_config | per-language rule chosen over default |
| AC-2 | tests/test_model_router.py::TestProviderRoutingRules::test_config_only_change_routes_new_language | new fixture language routes to its rule with no code change |
| AC-3 | tests/test_model_router.py::TestResolveRouteGroupsPerLanguage::test_each_target_resolved_independently | two distinct languages → two RouteGroups |
| AC-3 | tests/test_model_router.py::TestResolveRouteGroupsPerLanguage::test_first_target_not_used_for_all | second language NOT in first group's targets |
| AC-4 | tests/test_model_router.py::TestResolveRouteGroupsPerLanguage::test_mixed_batch_vi_de_ko_ja_groups | batch partitions vi/de/ko/ja by their rule models |
| AC-4 | tests/test_model_router.py::TestResolveRouteGroupsPerLanguage::test_mixed_batch_group_models_match_rules | each group's model == fixture rule model |
| AC-5 | tests/test_model_router.py::TestProviderRoutingRules::test_unlisted_language_falls_back_to_default | unmapped language resolves to routing.default |
| AC-5 | tests/test_model_router.py::TestProviderRoutingRules::test_default_fallback_no_crash | no exception; valid RouteGroup returned |
| AC-6 | tests/test_model_router.py::TestResolveRoute | pre-existing routing behavior unchanged |
| AC-6 | tests/test_model_router.py::TestResolveRouteGroups | pre-existing grouping unchanged in intent (see Test Update Contract for the vi/ja/de group-count case) |
| AC-6 | tests/test_model_router.py::TestGreedyPreset | unchanged |
| AC-6 | tests/test_model_router.py::TestGetRouteInfo | unchanged |
| AC-6 | tests/test_model_router.py::TestLegacyOllamaPath::test_provider_config_none_uses_ollama_grouping | provider_config=None still uses Ollama grouping |
| AC-6 | tests/test_model_router.py::TestLegacyOllamaPath::test_legacy_profile_override_non_auto_returns_none | non-auto override returns None |
| AC-6 | tests/test_hy_mt_quality_refinement.py::TestRouteGroupRefineModel | legacy refine_model grouping untouched |
| AC-7 | cdd-kit validate --contracts (contracts/business/business-rules.md) | contract validates; BR-18/BR-19/Table D present |

## Handoff Constraints

- Implementation agents must not infer missing requirements from chat history.
- Do not re-copy full design, test strategy, CI policy, or contract prose into this plan; follow the source pointers above.
- If this plan omits a required file, behavior, contract, or test, stop and report `blocked`.
- Keep implementation within the file-level plan unless a Context Expansion Request is approved.
- Do NOT modify `app/backend/api/routes.py`, `app/backend/services/job_manager.py`,
  `orchestrator.py`, `translation_service.py`, or any workflow file — they are
  outside scope (see Consumer Compatibility and Contract Updates).
- Constraints reaffirmed: no new clients, no new fallback logic, no new API
  endpoints (change-classification.md scope; ADR-0001 Consequences).

## Known Risks

- Source-of-truth gap: if `config/providers.yml` `routing.rules` omits any of the
  four languages the legacy table covered (vi/de/ja/ko), that language silently
  falls back to `routing.default` in the cloud path. Mitigation: IP-4 must cover
  all four; AC-5 fallback tests confirm no crash on the miss path.
- `routing.rules` shape discrepancy between BR-4 prose ("list of
  `{lang, model, provider, profile}`") and test-plan.md Fixture Shape (language-keyed
  map). Implemented as map-keyed (tests are executable spec). Route to
  `contract-reviewer` to reconcile BR-4 wording; do not edit the contract here.
- Group-count shift: `TestResolveRouteGroups::test_vietnamese_japanese_german_gives_one_group`
  asserts the legacy Ollama path groups vi/ja/de into one group. That test uses
  `provider_config=None` (legacy path), which is unchanged by this plan, so it
  should stay green — but per test-plan.md Test Update Contract, if per-language
  resolution unexpectedly changes its count, update only that count, not its
  intent. The cloud-path grouping (provider_config present) is the only branch
  that changes shape.
- `model_type` derivation for cloud rules: IP-2 keeps the existing default-branch
  `model_type` derivation (`"general"` for cloud). If a future rule needs a
  distinct `model_type`, that is out of scope here.
- Code map currency: `.cdd/code-map.yml` was generated 2026-06-17 and matches the
  read source ranges; no staleness observed for the files in scope.
