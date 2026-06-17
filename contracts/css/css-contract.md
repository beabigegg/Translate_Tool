---
contract: css
summary: UI token policy, component styling rules, and visual review constraints.
owner: application-team
surface: ui
schema-version: 0.1.0
last-changed: 2026-04-27
breaking-change-policy: deprecate-2-minors
---

# CSS / UI Contract

## Token Source of Truth

Design tokens are defined in `contracts/css/design-tokens.md` and implemented in `app/frontend/src/styles/`. CSS variables are the canonical runtime token form; hardcoded hex/px values in component files are forbidden.

## Component Rules
| component | variants | states | responsive behavior | allowed overrides |
|---|---|---|---|---|
| TranslatePage | — | loading, error, complete | single-column, scrollable | none — layout via CSS vars only |

## Forbidden Practices
- hard-coded visual tokens when token system exists
- global leakage from feature styles
- unreviewed shared component overrides
- unreviewed z-index additions

## Visual Review Policy
