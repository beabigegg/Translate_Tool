---
contract: css
summary: UI token policy, component styling rules, and visual review constraints.
owner: application-team
surface: ui
schema-version: 0.2.0
last-changed: 2026-06-20
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

## Forbidden Practices
- hard-coded visual tokens when token system exists
- global leakage from feature styles
- unreviewed shared component overrides
- unreviewed z-index additions

## Visual Review Policy
