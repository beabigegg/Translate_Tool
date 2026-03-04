# Change: Add VRAM Settings Panel

## Why
Users currently have no visibility into GPU VRAM usage and must adjust `num_ctx` via environment variables. With the multi-model system (general 4B vs HY-MT 7B), different models consume vastly different VRAM. A frontend VRAM calculator panel lets users see estimated VRAM usage for their selected profile and optionally override `num_ctx` per job to balance quality vs VRAM constraints.

## What Changes
- Add per-model-type VRAM metadata (`model_size_gb`, `kv_per_1k_ctx_gb`) to backend config
- Add `GET /api/model-config` endpoint returning VRAM metadata and default `num_ctx` per model type
- Add optional `num_ctx` field to `POST /api/jobs` for per-job override
- Thread per-job `num_ctx` through job_manager → orchestrator → OllamaClient `_build_options()`
- Add VRAM calculator panel in frontend Advanced Settings showing estimated VRAM for selected profile
- Add `num_ctx` slider in the VRAM panel with real-time VRAM recalculation

## Impact
- Affected specs: `frontend-ui` (VRAM panel, num_ctx slider), `translator-core` (Web Frontend UI, Web API Service), `translation-backend` (per-job num_ctx override, VRAM metadata)
- Affected code: `config.py`, `routes.py`, `schemas.py`, `job_manager.py`, `orchestrator.py`, `ollama_client.py`, `App.jsx`, `api.js`, `styles.css`
- Depends on: archived change `2026-03-04-add-multi-model-selection` (model type system, `MODEL_TYPE_OPTIONS`)
- No breaking changes: `num_ctx` override is optional; when absent, per-model-type defaults apply
