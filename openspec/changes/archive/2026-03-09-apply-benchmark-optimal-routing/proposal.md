# Change: Apply Benchmark-Driven Optimal Model Routing

## Why
Full-factorial benchmark (24 settings × 150 sentence pairs × 10 language pairs) and real-file pipeline benchmark (5 settings × 2 files × 2 languages) identified that different models perform best for different target languages. Currently, the user must manually choose a Translation Profile (model + prompt) which is error-prone and ignores per-language performance data. The frontend also exposes 55+ languages and complex profile selection that most users don't need.

## What Changes
- **New model routing module** — auto-selects the best model, profile, and decode parameters per target language based on benchmark results
- **Greedy decode as default** — benchmark proved greedy (temp=0.05, top_p=0.50, top_k=10) outperforms all models' official parameters
- **Simplified frontend** — reduce target languages to 8 commonly-used ones, hide profile selection behind Advanced Settings, remove source language selector from main view
- **Route info API** — new endpoint so frontend can show which model will be used per language

## Impact
- Affected specs: `model-routing` (new), `frontend-ui`, `translation-backend`
- Affected code:
  - `app/backend/services/model_router.py` (new)
  - `app/backend/config.py` (decode defaults)
  - `app/backend/api/routes.py` (auto_route, route-info endpoint)
  - `app/backend/api/schemas.py` (new response types)
  - `app/frontend/src/App.jsx` (UI simplification)
  - `app/frontend/src/api.js` (new API call)
