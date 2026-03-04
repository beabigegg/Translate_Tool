## Context

The multi-model system (`add-multi-model-selection`) introduced per-model-type `num_ctx` defaults in `MODEL_TYPE_OPTIONS`. Users have no way to see or override these values from the frontend. Different models consume very different VRAM (qwen3.5:4b ~3.5GB vs HY-MT 7B ~5.7GB), making `num_ctx` tuning important for 8GB GPUs.

## Goals / Non-Goals

- Goals:
  - Show estimated VRAM usage in the frontend for the selected profile
  - Allow per-job `num_ctx` override via a slider
  - Real-time VRAM recalculation as `num_ctx` changes
  - Backend API for VRAM metadata to avoid hardcoding sizes in frontend

- Non-Goals:
  - Auto-detecting actual GPU VRAM capacity (user inputs their GPU size or uses default 8GB)
  - Adjusting batch_size, timeout, or other inference parameters from frontend
  - Persistent translation settings — `num_ctx` override resets to the model-type default each session (GPU capacity is a display preference persisted to localStorage, not a translation setting)

## Decisions

- **Decision: VRAM metadata in backend config, not queried from Ollama**
  - Ollama's `/api/show` returns model details but not VRAM estimates in a reliable format
  - We define `VRAM_METADATA` dict in `config.py` mapping `ModelType` to `{model_size_gb, kv_per_1k_ctx_gb}`
  - Frontend computes: `total_vram = model_size_gb + (num_ctx / 1024) * kv_per_1k_ctx_gb`
  - Values: general (qwen3.5:4b Q4_K_M): `{model_size_gb: 3.5, kv_per_1k_ctx_gb: 0.35}`; translation (HY-MT 7B Q4_K_M): `{model_size_gb: 5.7, kv_per_1k_ctx_gb: 0.22}`
  - Alternative: query Ollama at runtime — adds latency, unreliable across versions

- **Decision: Per-job `num_ctx` override, not global mutation**
  - `POST /api/jobs` accepts optional `num_ctx` field
  - When absent, per-model-type default from `MODEL_TYPE_OPTIONS` is used
  - Override is threaded: routes → job_manager → orchestrator → `OllamaClient._build_options()`
  - `_build_options()` checks `self._num_ctx_override` before falling back to `MODEL_TYPE_OPTIONS`
  - Alternative: global `PUT /api/config` — adds state management complexity and concurrency issues

- **Decision: VRAM panel inside Advanced Settings, not a separate card**
  - The VRAM panel is a new `.setting-group` inside the existing collapsible Advanced Settings card
  - Renders below the PDF settings
  - Contains: VRAM usage bar, model size breakdown, num_ctx slider
  - Alternative: separate card — adds visual clutter for a single slider

- **Decision: GPU capacity defaults to 8GB, user can change**
  - A small dropdown or input above the VRAM bar lets users set their GPU VRAM (6/8/10/12/16/24 GB)
  - Default: 8 (matching the RTX 4060 baseline in project.md)
  - Stored in `localStorage` so it persists across sessions
  - VRAM bar color: green (<75%), yellow (75-90%), red (>90%)

## Risks / Trade-offs

- **VRAM estimates are approximate** — Actual VRAM usage depends on Ollama internals, OS overhead, and other running processes. Displayed as "estimated" with a note.
- **Hardcoded model sizes** — If user changes to a different quantization of the same model, sizes will be wrong. Mitigated by using the `HYMT_DEFAULT_MODEL` constant tag and documenting the expected quant level.
