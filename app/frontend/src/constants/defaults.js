export const DEFAULT_GPU_VRAM = 8;
export const DEFAULT_SRC_LANG = 'auto';
export const DEFAULT_PROFILE = 'general';
export const HISTORY_MAX_ENTRIES = 50;
// translation-progress-detail-ui: display-only approximation of the backend's
// JUDGE_MAX_ITERATIONS config default (app/backend/config.py). Not fetched
// per-poll (no new endpoint/field per ADR-0010) — a job whose backend was
// started with a different JUDGE_MAX_ITERATIONS env override will show this
// approximate denominator, which is informational only.
export const JUDGE_MAX_ITERATIONS_DISPLAY = 3;
