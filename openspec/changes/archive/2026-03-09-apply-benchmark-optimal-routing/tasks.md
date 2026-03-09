## 1. Backend: Model Router Module
- [x] 1.1 Create `app/backend/services/model_router.py` with routing table and `resolve_route()` function
- [x] 1.2 Add unit test `tests/test_model_router.py` — verify routing for Vietnamese→HY-MT, English→Qwen, Japanese→HY-MT, Korean→tgemma, unlisted→Qwen, and manual override

## 2. Backend: Update Decode Defaults
- [x] 2.1 Update `MODEL_TYPE_OPTIONS` in `app/backend/config.py` to use greedy decode parameters for both model types
- [x] 2.2 Verify existing `translation_strategy.py` per-scenario overrides still apply on top of new defaults

## 3. Backend: API Route Changes
- [x] 3.1 Modify `POST /api/jobs` in `app/backend/api/routes.py` to call `resolve_route()` when profile is `None` or `"auto"`
- [x] 3.2 Add `GET /api/route-info` endpoint returning model info per target language
- [x] 3.3 Add `RouteInfoResponse` schema in `app/backend/api/schemas.py`

## 3b. Backend: Per-Target-Group Model Routing
- [x] 3b.1 Add `resolve_route_groups()` in `model_router.py` — groups targets by (model, profile_id, model_type), returns list of `RouteDecision` with grouped targets
- [x] 3b.2 Update `routes.py` `create_job()` — call `resolve_route_groups()` instead of `resolve_route()`, pass route groups to `job_manager.create_job()`
- [x] 3b.3 Update `job_manager.py` `create_job()` — accept route groups, loop `process_files()` per group with group's model/profile/targets, accumulate processed counts
- [x] 3b.4 Update `tests/test_model_router.py` — add tests for grouping: [English, Vietnamese] → 2 groups, [Vietnamese, Japanese, German] → 1 group, manual override → 1 group with override model

## 4. Frontend: Simplify Target Language Selection
- [x] 4.1 Replace `LANG_GROUPS` with `TARGET_LANGUAGES` array (8 languages with bilingual labels)
- [x] 4.2 Replace `LanguageSelector` component with compact checkbox grid for target languages
- [x] 4.3 Remove the Output Order reorder UI (keep selection order as output order)

## 5. Frontend: Layout and Profile Changes
- [x] 5.1 Change from 3-column to 2-column layout (left: upload + targets, right: status + settings)
- [x] 5.2 Move profile selector into Advanced Settings as dropdown with "自動 (Auto)" default
- [x] 5.3 Move source language selector into Advanced Settings
- [x] 5.4 Add route info display showing auto-selected model name

## 6. Frontend: API Integration
- [x] 6.1 Add `fetchRouteInfo(targets)` function in `app/frontend/src/api.js`
- [x] 6.2 Call route info API when targets change and auto-routing is active
- [x] 6.3 Update `handleStart` to omit profile field when auto-routing

## 7. Validation
- [ ] 7.1 Run backend with new defaults, verify translation works end-to-end
- [ ] 7.2 Verify auto-routing selects correct models: English→Qwen, Vietnamese→HY-MT (even in same job)
- [ ] 7.3 Verify manual profile override still works (all targets use override model)
- [ ] 7.4 Verify frontend renders correctly in two-column layout
