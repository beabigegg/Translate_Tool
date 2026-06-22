---
contract: css
summary: UI token policy, component styling rules, and visual review constraints.
owner: application-team
surface: ui
schema-version: 0.3.0
last-changed: 2026-06-22
breaking-change-policy: deprecate-2-minors
---

# CSS / UI Contract

## Token Source of Truth

Design tokens are defined in `contracts/css/design-tokens.md` and implemented in `app/frontend/src/styles/`. CSS variables are the canonical runtime token form; hardcoded hex/px values in component files are forbidden.

## Component Rules
| component | variants | states | responsive behavior | allowed overrides |
|---|---|---|---|---|
| TranslatePage | — | loading, error, complete | single-column, scrollable | none — layout via CSS vars only |
| SettingsPage | — | loading, error, configured, unconfigured | single-column, scrollable | none — layout via CSS vars only |
| ProviderStatusBadge | online, offline, not_configured | — | inline, no wrapping | color via CSS vars only — never hardcoded |
| DeepSeekKeyInput | filled, empty, masked | focused, disabled | full-width within settings card | none |
| TestTranslationPanel | idle, running, done, error | per-result: success, error | grid or list of result cards | result-card gap and padding via CSS vars only |
| JudgePanel | available, disabled, unavailable | loading, idle | single-column within job detail card; hidden (renders nothing) when judge_status = disabled or unavailable | none — layout via CSS vars only |
| JudgeBadge | 高 (green), 中 (yellow), 低 (red) | — | inline within JudgePanel; text color via CSS vars only | color via CSS vars only — never hardcoded |
| JudgeApplyButton | active, disabled | focused, loading | full-width within JudgePanel; visible only when score ∈ {中, 低} and retranslated_blocks is non-empty | none |
| JudgeApplyDialog | idle, loading, confirmed, cancelled | — | modal overlay; z-index via CSS vars only; shows re-translated text preview and confirm/cancel | dialog gap and padding via CSS vars only |

**JudgePanel visibility rule:** When `judge_status` is `"disabled"` or `"unavailable"`, the `JudgePanel` component MUST render nothing (clean absence — no placeholder, no empty card, no spinner after load). When `judge_status` is `"available"`, the panel renders the score badge, source text, translated text (judge's accepted draft), feedback text, and attempt count.

**JudgeBadge color tokens:** 高 uses `--color-quality-high` (green family); 中 uses `--color-quality-mid` (yellow/amber family); 低 uses `--color-quality-low` (red family). These token names must be defined in `contracts/css/design-tokens.md` before implementation ships. Hardcoded hex values in the badge are forbidden per the Forbidden Practices clause.

**JudgeApplyDialog:** Confirms the destructive overwrite (BR-75). Must display: (1) a summary of the re-translated text the user is about to apply; (2) a clear warning that the current download file will be overwritten with no backup. On confirm, fires POST /api/jobs/{id}/judge/apply. On cancel, closes without side-effect.

**JudgeApplyButton state:** The button is disabled (and the apply dialog is not reachable) when `judge_apply_status` is `"applied"` (already applied) or `"applying"` (in progress). When `judge_apply_status` is `"failed"`, the button re-enables and shows a retry affordance.

## Forbidden Practices
- hard-coded visual tokens when token system exists
- global leakage from feature styles
- unreviewed shared component overrides
- unreviewed z-index additions

## Visual Review Policy
