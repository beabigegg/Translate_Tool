## 1. Backend: VRAM Metadata & Config Endpoint

- [x] 1.1 Add `VRAM_METADATA` dict to `config.py` mapping `ModelType` to `{model_size_gb, kv_per_1k_ctx_gb, default_num_ctx, min_num_ctx, max_num_ctx}`
- [x] 1.2 Add `ModelConfigItem` schema to `schemas.py` with fields: `model_type`, `model_size_gb`, `kv_per_1k_ctx_gb`, `default_num_ctx`, `min_num_ctx`, `max_num_ctx`
- [x] 1.3 Add `GET /api/model-config` endpoint in `routes.py` returning list of `ModelConfigItem`

## 2. Backend: Per-Job num_ctx Override

- [x] 2.1 Add optional `num_ctx: Optional[int] = Form(None)` parameter to `POST /api/jobs` in `routes.py`; validate against resolved model type's `[min_num_ctx, max_num_ctx]` range, return HTTP 422 if out of bounds
- [x] 2.2 Pass `num_ctx` through `job_manager.create_job()` → `_run_job()` → `process_files()`
- [x] 2.3 Pass `num_ctx` through `orchestrator.process_files()` → `OllamaClient` constructor
- [x] 2.4 Add `num_ctx_override` parameter to `OllamaClient.__init__()` and use in `_build_options()` (override takes priority over `MODEL_TYPE_OPTIONS` default)
- [x] 2.5 Include `num_ctx` in the `[CONFIG]` log line when overridden

## 3. Frontend: VRAM Calculator Panel

- [x] 3.1 Add `fetchModelConfig()` function to `api.js`
- [x] 3.2 Add state: `modelConfig` (array), `gpuVram` (number, default 8, persisted to localStorage), `numCtxOverride` (number or null)
- [x] 3.3 Fetch model config on mount alongside `fetchProfiles()`
- [x] 3.4 Add VRAM settings group inside Advanced Settings with: GPU capacity selector, num_ctx slider, VRAM usage bar
- [x] 3.5 Compute and display estimated VRAM: `model_size_gb + (num_ctx / 1024) * kv_per_1k_ctx_gb`
- [x] 3.6 VRAM bar color: green (<75%), yellow (75-90%), red (>90%)
- [x] 3.7 When profile changes, reset `numCtxOverride` to null (use profile's default)
- [x] 3.8 Include `num_ctx` in FormData when overridden (non-null)

## 4. Frontend: CSS

- [x] 4.1 Add `.vram-bar` styles (height, border-radius, color states)
- [x] 4.2 Add `.vram-info` text styles for model size breakdown

## 5. Verification

- [x] 5.1 Verify `GET /api/model-config` returns metadata for both model types
- [x] 5.2 Submit job with `num_ctx` override, verify backend logs show overridden value
- [x] 5.3 Submit job without `num_ctx`, verify default per-model-type value used
- [x] 5.4 Submit job with out-of-range `num_ctx`, verify HTTP 422 returned
- [x] 5.5 Verify VRAM bar updates in real-time when slider moves
- [x] 5.6 Verify VRAM bar resets when switching profiles
