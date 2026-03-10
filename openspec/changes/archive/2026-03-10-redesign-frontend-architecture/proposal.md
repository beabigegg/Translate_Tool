# Change: Redesign Frontend Architecture

## Why
The current frontend is a single-file monolith (`App.jsx` at 1730 lines) containing 15+ components, 20+ useState hooks, 15+ inline SVGs, and all business logic. This makes the codebase unmaintainable, prevents independent feature development, and results in a UI that is functional but unintuitive for non-developer users. Key issues include: no routing (everything on one page), mixed Chinese/English UI text, term management crammed into an overlay panel, important settings hidden in a collapsible "Advanced Settings" section, decorative step indicator that isn't interactive, no notification system (uses `alert()`), and multiple backend APIs (`/api/health`, `/api/stats`, `/api/cache/stats`, `/api/terms/wikidata/*`) with no frontend integration.

## What Changes

### Architecture
- **BREAKING**: Decompose `App.jsx` monolith into modular component/page/hook/constant structure
- **BREAKING**: Introduce client-side routing with `react-router-dom` (5 routes: `/`, `/terms`, `/terms/review`, `/settings`, `/history`)
- Replace 20+ flat `useState` with `useReducer` for translation workflow state
- Add `React Context` for cross-page shared settings (theme, VRAM, defaults)
- Split `api.js` into domain-specific modules (`jobs.js`, `terms.js`, `system.js`, `config.js`) with unified error handling
- Split `styles.css` into modular CSS files (tokens, reset, base, per-component)

### UI/UX
- Persistent sidebar navigation + top bar shell layout (replaces single-page layout)
- Translation workflow becomes interactive 3-step wizard (upload → language/settings → progress/download)
- Term database management promoted from overlay panel to full pages (`/terms`, `/terms/review`)
- All settings consolidated into dedicated settings page (`/settings`)
- New translation history page (`/history`) using localStorage
- Source language and translation profile moved from hidden Advanced Settings to visible step-2 fields
- Replace all `alert()` calls with toast notification system (`sonner`)
- Replace 15+ inline SVGs with `lucide-react` icon library
- Add dark mode toggle with CSS custom property theming
- Lightweight i18n system (key-value, no framework) defaulting to Traditional Chinese

### New Integrations
- Health check indicator (sidebar, calls `GET /api/health` every 30s)
- Cache management UI (settings page, calls `GET /api/cache/stats` + `DELETE /api/cache`)
- Translation statistics display (history page, calls `GET /api/stats`)

## Impact
- Affected specs: `frontend-ui` (major modifications to all 12 existing requirements)
- Affected code: `app/frontend/src/` (complete restructure)
- New dependencies: `react-router-dom`, `lucide-react`, `sonner` (3 packages)
- No backend changes required — all backend APIs already exist
- Migration strategy: 5 phases, each independently testable
