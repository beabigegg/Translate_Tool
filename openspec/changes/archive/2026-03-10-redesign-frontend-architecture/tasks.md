## Phase 1: Foundation (基礎架構)

- [x] 1.1 Install dependencies: `react-router-dom`, `lucide-react`, `sonner`
- [x] 1.2 Create folder structure: `components/{ui,layout,feedback,domain}`, `pages/`, `hooks/`, `contexts/`, `api/`, `constants/`, `i18n/`, `styles/`
- [x] 1.3 Extract CSS tokens from `styles.css` lines 1-135 into `styles/tokens.css`; create `styles/reset.css`, `styles/base.css`
- [x] 1.4 Create `styles/theme-dark.css` with dark mode CSS custom property overrides
- [x] 1.5 Build `api/client.js` — unified fetch wrapper with error handling
- [x] 1.6 Split `api.js` into `api/jobs.js`, `api/terms.js`, `api/system.js`, `api/config.js`
- [x] 1.7 Extract constants from `App.jsx` lines 1-50 into `constants/languages.js`, `constants/fileTypes.js`, `constants/defaults.js`
- [x] 1.8 Build basic UI primitives: `Button`, `Card`, `Input`, `Select`, `Checkbox`, `Badge`, `Tabs`
- [x] 1.9 Build layout components: `AppShell`, `Sidebar`, `TopBar`, `PageHeader`
- [x] 1.10 Set up `react-router-dom` routes in `App.jsx` with placeholder page components
- [x] 1.11 Build `HealthIndicator` component in sidebar bottom — polls `GET /api/health` every 30s
- [x] 1.12 Integrate `sonner` Toaster at AppShell level; create `hooks/useNotification.js`
- [x] 1.13 Create `contexts/SettingsContext.jsx` — manages theme, VRAM, default languages, persists to localStorage
- [x] 1.14 Create `hooks/useTheme.js` — dark mode toggle with `data-theme` attribute and `prefers-color-scheme` support
- [x] 1.15 Verify: all routes render placeholder content, sidebar navigates correctly, health indicator polls

## Phase 2: Translation Workspace (翻譯工作台)

- [x] 2.1 Build `StepWizard` component — 3 steps, clickable navigation, locked during active job
- [x] 2.2 Build `TranslatePage` with `useReducer` managing wizard state (step, files, targets, srcLang, profile, jobMode, jobId, jobStatus, error, loading)
- [x] 2.3 Migrate `FileDropZone` and `FileCard` from `App.jsx` into `components/domain/`; add file type validation feedback
- [x] 2.4 Build step 1 (Upload): FileDropZone + FileList + "下一步" button (enabled only when files > 0)
- [x] 2.5 Build `LanguageGrid` component — checkbox grid for target languages with "展開完整語言列表" toggle
- [x] 2.6 Build `RouteInfoDisplay` component — shows model routing info from `GET /api/route-info`
- [x] 2.7 Build step 2 (Language & Settings): left column (LanguageGrid + RouteInfo), right column (mode toggle, srcLang dropdown, profile dropdown, PDF settings conditional)
- [x] 2.8 Build `TranslationProgress` component — overall progress bar, per-file progress, stats cards (file count, segment count, speed, ETA)
- [x] 2.9 Build step 3 (Progress & Download): TranslationProgress + download/cancel/reset buttons
- [x] 2.10 Migrate `hooks/useJobPolling.js` — poll job status, dispatch to reducer, save history to localStorage on completion
- [x] 2.11 Replace all `alert()` calls with toast notifications in translation flow
- [x] 2.12 Verify: complete translation flow works end-to-end (upload → configure → translate → download)

## Phase 3: Term Management (術語庫)

- [x] 3.1 Build `TermsPage` with tabs: "總覽", "待審核 (N)", "已核准", "匯入匯出"
- [x] 3.2 Build overview tab — stat cards (total, pending, approved), breakdown by language and domain charts
- [x] 3.3 Build `TermCard` component — displays source/target, metadata, action buttons
- [x] 3.4 Build `TermsReviewPage` — unverified term list with filter (language, domain), search, inline edit
- [x] 3.5 Implement inline editing: click "編輯" → input field → Enter saves + approves, Escape cancels
- [x] 3.6 Implement batch approval: "全部核准" with confirmation dialog
- [x] 3.7 Build approved terms tab — sortable by usage count, alphabetical, last modified
- [x] 3.8 Build import/export tab — format selector (JSON/CSV/XLSX), conflict strategy selector, result display
- [x] 3.9 Replace all `alert()` calls in term operations with toast notifications
- [x] 3.10 Verify: term CRUD operations work, filters work, import/export works, toasts appear correctly

## Phase 4: Settings & History (設定與歷史)

- [x] 4.1 Build `SettingsPage` with sections: "系統狀態", "GPU 與記憶體", "翻譯預設值", "PDF 輸出設定", "介面"
- [x] 4.2 Build system status section — Ollama connection, available models, cache stats + clear cache button
- [x] 4.3 Migrate `VramCalculator` to settings GPU section — GPU capacity selector, num_ctx slider, VRAM usage bar
- [x] 4.4 Build translation defaults section — default source language, default profile, default target languages
- [x] 4.5 Build interface section — theme toggle (淺色/暗色/跟隨系統), language selector (繁中/English)
- [x] 4.6 Build `HistoryPage` — job list from localStorage, stats summary, empty state
- [x] 4.7 Implement `hooks/useLocalStorage.js` for history persistence (cap 50 entries FIFO)
- [x] 4.8 Verify: settings persist across page reloads, cache clear works, dark mode toggles correctly, history entries appear after translations

## Phase 5: Polish (精修)

- [x] 5.1 Create `i18n/zh-TW.js` and `i18n/en.js` with all UI strings; create `i18n/index.js` with `useTranslation()` hook
- [x] 5.2 Replace all hardcoded UI strings across all components with i18n keys
- [x] 5.3 Add entrance/exit animations: file cards (slide-in), term approval (slide-out), toast (slide-in from right)
- [x] 5.4 Add `ErrorBoundary` component wrapping each page route
- [x] 5.5 Implement lazy loading for page components via `React.lazy` + `Suspense`
- [x] 5.6 Accessibility audit: keyboard navigation, focus trap for modals, aria-live for progress, skip links
- [x] 5.7 Remove all legacy code: delete old `App.jsx` monolith, old `api.js`, old `styles.css` (after confirming all functionality migrated)
- [x] 5.8 Final verification: all 5 pages functional, all API integrations working, dark mode consistent, i18n switching works, responsive at all breakpoints
