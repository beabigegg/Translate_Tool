## Context

Benchmark data (March 2026) across 3 models × multiple factors shows:
- **Qwen3.5:4b** is best for zh→en (Final=34.48) and most directions
- **HY-MT1.5-7B** is best for zh→vi, zh→de, zh→ja (Qwen catastrophic at zh→ja=11.97)
- **TranslateGemma:4b** is best for zh→ko (marginal)
- **Greedy decode** (temp=0.05, top_p=0.50, top_k=10) is universally optimal
- **SysPrompt=ON** is the most impactful factor (+1.23 Final score)

The system currently requires users to manually select a profile. This proposal adds automatic model selection.

## Goals / Non-Goals

**Goals:**
- Auto-select best model per target language without user intervention
- Simplify UI for factory floor operators (non-technical users)
- Apply benchmark-optimal decode parameters as defaults
- Preserve manual override capability for power users

**Non-Goals:**
- Chain translation (e.g., zh→en→vi)
- Dynamic A/B testing or online learning

## Decisions

### Decision 1: Per-target-group model routing
Group targets by their optimal model and run `process_files()` once per group. Each group shares the same (model, profile, model_type) tuple, producing its own set of output files.

**Rationale:** Benchmark data shows dramatic quality differences per language—e.g., Qwen zh→ja scores Final=11.97 while HY-MT scores much higher. Using a single model for all targets wastes the routing table. Since `process_files()` already accepts a `targets` list, grouping targets and calling it multiple times is minimally invasive.

**Implementation approach:** `job_manager.create_job()` receives a list of `RouteDecision` groups. The `_run_job` inner function iterates over groups, calling `process_files()` once per group with the group's model/profile/targets. All groups share the same input files, output directory, stop flag, and job logging.

**Alternative considered:** Single-model-per-job (route on first target) — rejected because it silently degrades quality for non-primary targets.

### Decision 2: Routing table in dedicated module
Create `app/backend/services/model_router.py` with a static routing table. This keeps routing logic isolated and testable.

**Alternative considered:** Embedding routing in `routes.py` — rejected for separation of concerns.

### Decision 3: Greedy as universal default
Replace all per-model-type decode defaults in `config.py` with greedy parameters. The dynamic scenario strategy (`translation_strategy.py`) already overrides these per-scenario, so greedy serves as a safe baseline.

### Decision 4: Frontend two-column layout
Reduce from 3 columns to 2 columns. Target language becomes a compact checkbox grid in the left column alongside file upload. Profile override and source language move into Advanced Settings.

## Risks / Trade-offs

- **Risk:** Routing table becomes stale as models improve → **Mitigation:** Table is a simple dict, easy to update after re-benchmarking
- **Risk:** Multi-group jobs take longer (sequential model passes) → **Mitigation:** 8GB VRAM only supports one model at a time anyway; sequential is the only option. File processing per group is independent so outputs accumulate correctly
- **Risk:** Hiding profile selection confuses power users → **Mitigation:** Profile override remains in Advanced Settings with clear labeling

## Open Questions
- None at this time; all decisions informed by benchmark data
