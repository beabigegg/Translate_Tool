## Context

The Translate Tool frontend was built as a rapid prototype and evolved into a production tool without architectural refactoring. The entire UI lives in 4 flat files (`App.jsx`, `api.js`, `styles.css`, `main.jsx`), with `App.jsx` containing 1730 lines of mixed concerns. The backend API surface is well-designed and stable — this change is frontend-only.

**Constraints:**
- 8GB VRAM GPU — frontend must display VRAM estimates accurately
- Primary users are translators (not developers) — UI must be self-explanatory
- Desktop-first usage (tablet secondary, mobile low priority)
- Existing CSS Design Token system is well-built and should be preserved
- No backend changes — all required APIs already exist

## Goals / Non-Goals

**Goals:**
- Decompose monolith into maintainable, testable modules
- Create intuitive navigation via routing and persistent sidebar
- Make translation workflow a guided wizard experience
- Promote term management to first-class pages
- Unify UI language (default Traditional Chinese with i18n support)
- Add system health visibility (Ollama status, VRAM, cache)
- Support dark mode

**Non-Goals:**
- No backend API changes
- No TypeScript migration in this phase (future consideration)
- No unit/integration test framework setup (separate change)
- No mobile-first design (desktop primary)
- No heavy framework adoption (no Redux, Tailwind, MUI)

## Decisions

### 1. Routing: react-router-dom v6
- **Decision**: Use `react-router-dom` for client-side routing with 5 top-level routes
- **Alternatives**: Single-page with tab switching, hash-based routing
- **Rationale**: URL-addressable pages enable bookmarking, browser back/forward, and clear mental model. react-router-dom is the de facto standard with excellent lazy loading support.

### 2. State Management: useReducer + React Context
- **Decision**: Use `useReducer` for complex page state (translation wizard), `React Context` for cross-page settings (theme, VRAM, language defaults)
- **Alternatives**: Redux, Zustand, Jotai
- **Rationale**: Application has limited cross-page state (only settings/theme). Translation workflow state is page-local. External state libraries add complexity without proportional benefit at this scale.

### 3. Icons: lucide-react
- **Decision**: Replace 15+ inline SVG definitions with `lucide-react`
- **Alternatives**: Keep inline SVGs, use heroicons, use react-icons
- **Rationale**: lucide-react provides tree-shakeable, consistently styled icons. Matches the existing line-icon aesthetic. Eliminates ~120 lines of SVG definitions from App.jsx.

### 4. Notifications: sonner
- **Decision**: Use `sonner` for toast notifications, replacing all `alert()` calls
- **Alternatives**: react-hot-toast, notistack, custom implementation
- **Rationale**: sonner is ~3KB, provides stacking, auto-dismiss, and persistent error toasts out of the box. Minimal API surface.

### 5. CSS Strategy: Preserve tokens + per-component CSS files
- **Decision**: Keep CSS custom properties system, split `styles.css` into `tokens.css`, `reset.css`, `base.css`, `theme-dark.css`, and per-component `.css` files
- **Alternatives**: CSS Modules, Tailwind CSS, CSS-in-JS
- **Rationale**: The existing Design Token system is well-crafted. Per-component CSS files provide sufficient scoping without build tool complexity. CSS Modules can be adopted incrementally later if needed.

### 6. i18n: Lightweight key-value system
- **Decision**: Simple `zh-TW.js` / `en.js` key-value files with a `useTranslation()` hook, no framework
- **Alternatives**: react-i18next, FormatJS
- **Rationale**: Only 2 languages needed. ~200 UI strings total. A full i18n framework would be overkill. The key-value approach can be upgraded to i18next later if more languages are needed.

### 7. History: localStorage (no backend)
- **Decision**: Store last 50 job records in localStorage
- **Alternatives**: New backend API, IndexedDB
- **Rationale**: Backend currently has no persistent job history API. localStorage is sufficient for single-user local tool. Can migrate to backend storage when API is available.

### 8. Dark Mode: CSS custom property theming via `data-theme` attribute
- **Decision**: Toggle `data-theme="dark"` on `<html>`, override CSS custom properties
- **Alternatives**: CSS class toggle, separate stylesheet, CSS-in-JS theme provider
- **Rationale**: Builds directly on existing CSS token infrastructure. No JavaScript runtime cost. Supports system preference via `prefers-color-scheme` media query.

## Folder Structure

```
app/frontend/src/
├── main.jsx
├── App.jsx                     # Router + AppShell
├── components/
│   ├── ui/                     # Button, Card, Input, Select, Checkbox, etc.
│   ├── layout/                 # AppShell, Sidebar, TopBar, PageHeader
│   ├── feedback/               # StatusDot, ErrorBoundary, Spinner
│   └── domain/                 # FileDropZone, LanguageGrid, StepWizard, TermCard, etc.
├── pages/                      # TranslatePage, TermsPage, TermsReviewPage, SettingsPage, HistoryPage
├── hooks/                      # useJobPolling, useHealthCheck, useLocalStorage, useTheme, useNotification
├── contexts/                   # SettingsContext
├── api/                        # client.js, jobs.js, terms.js, system.js, config.js
├── constants/                  # languages.js, fileTypes.js, defaults.js
├── i18n/                       # index.js, zh-TW.js, en.js
└── styles/                     # tokens.css, reset.css, base.css, theme-dark.css, utilities.css
```

## Risks / Trade-offs

| Risk | Impact | Mitigation |
|------|--------|------------|
| Large scope — touching all frontend code | Regression risk | 5-phase migration, each phase independently testable |
| No tests exist to catch regressions | Silent breakage | Manual testing checklist per phase; test framework is a follow-up change |
| localStorage history has size limits | Data loss after ~50 entries | Cap at 50 entries with FIFO; migrate to backend API later |
| 3 new npm dependencies | Bundle size increase | All are tree-shakeable; total addition ~15KB gzipped |
| Learning curve for new structure | Slower initial development | Clear folder conventions documented; component naming follows domain language |

## Migration Plan

### Phase 1: Foundation
- Install dependencies, create folder structure
- Extract CSS tokens to `styles/tokens.css`
- Build `AppShell` (sidebar + top bar) with routing skeleton
- Basic UI primitives (Button, Card, Input)
- All pages render placeholder content

### Phase 2: Translation Workspace
- Migrate translation workflow to `TranslatePage` with `useReducer`
- Implement `StepWizard` with interactive navigation
- Migrate `FileDropZone`, `FileCard`, `LanguageGrid`
- Integrate `sonner` for notifications
- Wire up job submission and polling

### Phase 3: Term Management
- Build `TermsPage` (overview + tabs)
- Build `TermsReviewPage` (filter, search, approve, edit)
- Migrate term import/export functionality
- Remove old `TermDBPanel` overlay

### Phase 4: Settings & History
- Build `SettingsPage` with all config sections
- Integrate `/api/health`, `/api/cache/stats` APIs
- Build `HistoryPage` with localStorage
- Implement dark mode toggle
- Implement i18n system

### Phase 5: Polish
- Unify all UI text to Traditional Chinese via i18n keys
- Animation and transition polish
- Accessibility audit (keyboard nav, ARIA, contrast)
- Lazy loading for page components
- Remove all legacy code from old `App.jsx`

## Open Questions
- None — all architectural decisions resolved during evaluation phase.
