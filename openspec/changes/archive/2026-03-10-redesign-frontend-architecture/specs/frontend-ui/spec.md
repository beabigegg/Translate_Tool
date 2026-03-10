## MODIFIED Requirements

### Requirement: Translation Profile Selector
The frontend SHALL display a profile selector on the translation workspace's step 2 (Language & Settings) that allows users to choose a translation profile before submitting a job. The selector SHALL be directly visible without expanding any collapsible section.

#### Scenario: Profile selector on step 2
- **GIVEN** the user is on step 2 (Language & Settings) of the translation wizard
- **WHEN** the right column renders
- **THEN** the profile selector SHALL appear as a dropdown (`<Select>`) labeled "翻譯情境"
- **AND** SHALL be directly visible without expanding any settings section
- **AND** the `general` profile SHALL be selected by default

#### Scenario: Profile selector rendering
- **GIVEN** the backend returns a list of profiles from `GET /api/profiles`
- **WHEN** the profile selector renders
- **THEN** each profile SHALL be displayed as an option with its `name` and `description`
- **AND** the `general` profile SHALL be selected by default

#### Scenario: Profile selection persists to job submission
- **GIVEN** the user selects the "semiconductor" profile
- **WHEN** the user clicks "開始翻譯"
- **THEN** the form data SHALL include `profile=semiconductor`
- **AND** SHALL NOT include a hardcoded `model` field

#### Scenario: Profile fetch failure fallback
- **GIVEN** the `GET /api/profiles` request fails
- **WHEN** the frontend handles the error
- **THEN** a fallback profile entry for "general" SHALL be shown
- **AND** a toast notification SHALL display the error (replacing previous silent failure)
- **AND** the user SHALL still be able to submit translation jobs

### Requirement: Remove Hardcoded Model
The frontend SHALL no longer hardcode a specific model name. Model selection SHALL be derived from the selected profile on the backend.

#### Scenario: No hardcoded model in frontend
- **GIVEN** the App component initializes
- **WHEN** state variables are declared
- **THEN** there SHALL be no hardcoded model string (e.g., `"translategemma:12b"`)
- **AND** the `model` form field SHALL be replaced by `profile`

### Requirement: Frontend State Management for Profiles
The SettingsContext SHALL manage profile data as shared state, while profile selection SHALL be local to the TranslatePage component via useReducer.

#### Scenario: Profile data in SettingsContext
- **GIVEN** the application mounts
- **WHEN** `SettingsContext` initializes
- **THEN** it SHALL fetch profiles from `GET /api/profiles` and store them in context
- **AND** on failure, set profiles to the fallback array and show a toast error notification

#### Scenario: Profile selection in TranslatePage reducer
- **GIVEN** the TranslatePage renders
- **WHEN** the translation workflow reducer initializes
- **THEN** `selectedProfile` SHALL default to `"general"`
- **AND** changing profile SHALL dispatch a `SET_PROFILE` action

#### Scenario: Profile state does not affect other state
- **GIVEN** the user changes the selected profile
- **WHEN** the profile state updates
- **THEN** no other state variables (files, selectedTargets, srcLang, etc.) SHALL be affected

### Requirement: Frontend API Integration for Profiles
The `api/config.js` module SHALL export a `fetchProfiles()` function for retrieving available profiles.

#### Scenario: fetchProfiles function
- **GIVEN** the `api/config.js` module
- **WHEN** `fetchProfiles()` is called
- **THEN** it SHALL send a GET request to `/api/profiles` via the shared API client
- **AND** return the parsed JSON response
- **AND** throw an Error on non-OK response (handled by unified error handler)

#### Scenario: Form submission with profile and optional num_ctx
- **GIVEN** the user clicks "開始翻譯"
- **WHEN** the TranslatePage submits the form
- **THEN** it SHALL append `form.append("profile", selectedProfile)`
- **AND** if `numCtxOverride` is not null, it SHALL append `form.append("num_ctx", numCtxOverride)`
- **AND** all other form fields SHALL remain unchanged

### Requirement: Profile Selector UI Component Structure
The profile selector SHALL be rendered as a dropdown select in the step 2 right column of the translation wizard.

#### Scenario: Dropdown position on step 2
- **GIVEN** the user is on step 2 of the translation wizard
- **WHEN** the right column renders
- **THEN** the profile selector SHALL appear as a `<Select>` component with label "翻譯情境"
- **AND** SHALL be positioned below the mode toggle and above PDF settings

#### Scenario: Profile selector interaction
- **GIVEN** the profile selector is displayed with "general" selected
- **WHEN** the user selects a different profile (e.g., "semiconductor")
- **THEN** the translation reducer SHALL dispatch `SET_PROFILE` with value `"semiconductor"`
- **AND** the route info display SHALL update to reflect model routing for the new profile

#### Scenario: Profile selector during translation
- **GIVEN** a translation job is in progress (step 3)
- **WHEN** the user attempts to navigate back to step 2
- **THEN** step navigation SHALL be locked during active translation
- **AND** the user SHALL NOT be able to change settings while a job is running

### Requirement: Source Language Auto-Detect Default
The frontend SHALL provide an "Auto-detect" option for source language selection on step 2 of the translation wizard.

#### Scenario: Auto-detect as default source language
- **GIVEN** the TranslatePage reducer initializes
- **WHEN** source language state is set
- **THEN** `srcLang` SHALL default to `"auto"`
- **AND** the source language dropdown SHALL display "自動偵測" as the first option

#### Scenario: Explicit source language selection
- **GIVEN** the user selects "English" from the source language dropdown on step 2
- **WHEN** the form is submitted
- **THEN** the `src_lang` form field SHALL be `"English"` (not `"auto"`)

#### Scenario: Auto-detect in form submission
- **GIVEN** the user leaves source language as "自動偵測"
- **WHEN** the form is submitted
- **THEN** the `src_lang` form field SHALL be `"auto"`

#### Scenario: Reset restores auto-detect default
- **GIVEN** the user previously selected "English" as source language
- **WHEN** the user clicks "開始新翻譯" (reset)
- **THEN** the reducer SHALL dispatch `RESET` and `srcLang` SHALL return to `"auto"`

### Requirement: handleReset Clears Profile Selection
The reset flow SHALL restore the translation wizard to its initial state including profile selection.

#### Scenario: Reset restores default profile
- **GIVEN** the user had selected "semiconductor" profile and completed a translation
- **WHEN** the user clicks "開始新翻譯" (reset)
- **THEN** the reducer SHALL dispatch `RESET`
- **AND** `selectedProfile` SHALL return to `"general"`
- **AND** the wizard SHALL return to step 1

### Requirement: VRAM Calculator Panel
The frontend SHALL display a VRAM calculator on the Settings page (`/settings`) under the "GPU 與記憶體" section.

#### Scenario: VRAM panel on settings page
- **GIVEN** the user navigates to `/settings`
- **WHEN** the settings page renders
- **THEN** a "GPU 與記憶體" section SHALL display: GPU capacity selector, num_ctx slider, estimated VRAM usage bar

#### Scenario: GPU capacity selector
- **GIVEN** the VRAM section is displayed
- **WHEN** the user selects a GPU capacity value
- **THEN** the available options SHALL include common VRAM sizes (6, 8, 10, 12, 16, 24 GB)
- **AND** the default SHALL be 8 GB
- **AND** the selected value SHALL be persisted to localStorage via SettingsContext

#### Scenario: num_ctx slider
- **GIVEN** the VRAM section is displayed
- **WHEN** the user adjusts the num_ctx slider
- **THEN** the slider range SHALL be bound by the selected profile's `min_num_ctx` and `max_num_ctx`
- **AND** the estimated VRAM SHALL recalculate in real time
- **AND** the current num_ctx value SHALL be displayed next to the slider

#### Scenario: VRAM usage bar display
- **GIVEN** a profile is selected and num_ctx is set
- **WHEN** the VRAM bar renders
- **THEN** it SHALL show estimated total VRAM as `model_size_gb + (num_ctx / 1024) * kv_per_1k_ctx_gb`
- **AND** display the breakdown: "模型: X.X GB + KV Cache: X.X GB = 總計: X.X GB"
- **AND** the bar color SHALL be green when usage < 75%, yellow when 75-90%, red when > 90%

### Requirement: Frontend Model Config API Integration
The `api/config.js` module SHALL export a `fetchModelConfig()` function for retrieving per-model-type VRAM and configuration metadata.

#### Scenario: fetchModelConfig function
- **GIVEN** the `api/config.js` module
- **WHEN** `fetchModelConfig()` is called
- **THEN** it SHALL send a GET request to `/api/model-config` via the shared API client
- **AND** return the parsed JSON response (array of model config objects)
- **AND** on failure, return a hardcoded fallback array with default values

#### Scenario: Model config fetched on mount
- **GIVEN** the application mounts
- **WHEN** SettingsContext initializes
- **THEN** it SHALL call `fetchModelConfig()` alongside `fetchProfiles()`
- **AND** store the result in context state

### Requirement: Extraction-Only Mode Trigger
The frontend SHALL provide a mode toggle on step 2 of the translation wizard that allows the user to run Phase 0 (term extraction) without proceeding to translation.

#### Scenario: Mode toggle on step 2
- **GIVEN** the user is on step 2 (Language & Settings) of the translation wizard
- **WHEN** the page renders
- **THEN** two mode options SHALL be displayed: "翻譯" and "僅萃取術語"
- **AND** "翻譯" SHALL be selected by default

#### Scenario: Extraction-only mode submission
- **GIVEN** the user selects "僅萃取術語" mode and clicks the action button
- **WHEN** the form is submitted
- **THEN** the request SHALL include `mode=extraction_only` in the form data
- **AND** the action button label SHALL read "開始萃取" instead of "開始翻譯"

#### Scenario: Extraction-only mode settings
- **GIVEN** the user selects "僅萃取術語" mode
- **WHEN** the mode is active
- **THEN** the profile selector and VRAM-related settings SHALL be visually de-emphasized
- **AND** only file upload and target language selection are required

### Requirement: Extraction Progress and Result Display
The frontend SHALL display progress during Phase 0 execution and show the extracted terms upon completion when running in extraction-only mode.

#### Scenario: Extraction progress display
- **GIVEN** an extraction-only job is running (step 3 of wizard)
- **WHEN** the job emits progress events
- **THEN** the UI SHALL display a progress bar with status message (e.g., "正在萃取術語… 第 N / M 段")

#### Scenario: Extraction result summary
- **GIVEN** an extraction-only job has completed
- **WHEN** the result is displayed on step 3
- **THEN** the UI SHALL show: total terms extracted, terms already in DB (skipped), new terms added
- **AND** a "前往術語庫審核" link SHALL navigate to `/terms/review`
- **AND** a toast notification SHALL announce completion

### Requirement: Term Database Management Panel
The frontend SHALL provide term database management as full pages accessible via the sidebar navigation, replacing the previous overlay panel.

#### Scenario: Term pages in navigation
- **GIVEN** the user is on any page
- **WHEN** the sidebar renders
- **THEN** a "術語庫" navigation item SHALL be visible
- **AND** clicking it SHALL navigate to `/terms`

#### Scenario: Term overview page
- **GIVEN** the user navigates to `/terms`
- **WHEN** the page renders
- **THEN** it SHALL display tabs: "總覽", "待審核 (N)", "已核准", "匯入匯出"
- **AND** the overview tab SHALL show: total count, breakdown by language, breakdown by domain

#### Scenario: Database statistics display
- **GIVEN** the user is on the terms overview tab
- **WHEN** statistics are loaded from `GET /api/terms/stats`
- **THEN** stat cards SHALL display: total term count, pending review count, approved count

#### Scenario: Export term database
- **GIVEN** the user is on the "匯入匯出" tab
- **WHEN** the user selects a format and clicks export
- **THEN** format options SHALL include: JSON, CSV, XLSX
- **AND** selecting a format SHALL trigger download via `GET /api/terms/export?format=<json|csv|xlsx>`

#### Scenario: Import term database
- **GIVEN** the user is on the "匯入匯出" tab
- **WHEN** the user selects a file and conflict strategy
- **THEN** strategy options SHALL include: 保留現有 (skip), 覆蓋 (overwrite), 依信心值合併 (merge)
- **AND** confirming SHALL POST to `/api/terms/import?strategy=<skip|overwrite|merge>`
- **AND** a toast notification SHALL display the result: "新增 N 筆、略過 N 筆、覆蓋 N 筆"

## ADDED Requirements

### Requirement: Application Shell Layout
The frontend SHALL render a persistent application shell with sidebar navigation and top bar across all pages.

#### Scenario: Shell layout structure
- **GIVEN** the application loads at any route
- **WHEN** the page renders
- **THEN** a sidebar (240px width) SHALL appear on the left with navigation items: "翻譯", "術語庫", "歷史紀錄", "設定"
- **AND** a top bar SHALL display the current page title and action area
- **AND** the main content area SHALL render the routed page component

#### Scenario: Sidebar system status
- **GIVEN** the sidebar renders
- **WHEN** the bottom section is visible
- **THEN** it SHALL display an Ollama connection status indicator (green/red dot)
- **AND** a mini VRAM usage bar showing current estimate
- **AND** the health status SHALL refresh by polling `GET /api/health` every 30 seconds

#### Scenario: Sidebar responsive collapse
- **GIVEN** the viewport width is between 768px and 1023px
- **WHEN** the sidebar renders
- **THEN** it SHALL collapse to icon-only mode (64px width)
- **AND** hovering SHALL temporarily expand to show text labels

#### Scenario: Mobile navigation
- **GIVEN** the viewport width is below 768px
- **WHEN** the page renders
- **THEN** the sidebar SHALL be replaced by a bottom navigation bar (56px height)
- **AND** it SHALL display 4 items: "翻譯", "術語庫", "歷史", "設定"

### Requirement: Client-Side Routing
The frontend SHALL use `react-router-dom` to provide client-side routing with URL-addressable pages.

#### Scenario: Route definitions
- **GIVEN** the application initializes
- **WHEN** the router mounts
- **THEN** the following routes SHALL be registered: `/` (TranslatePage), `/terms` (TermsPage), `/terms/review` (TermsReviewPage), `/settings` (SettingsPage), `/history` (HistoryPage)

#### Scenario: Navigation updates URL
- **GIVEN** the user clicks "術語庫" in the sidebar
- **WHEN** navigation occurs
- **THEN** the browser URL SHALL update to `/terms`
- **AND** the TermsPage component SHALL render in the main content area
- **AND** no full page reload SHALL occur

#### Scenario: Direct URL access
- **GIVEN** the user enters `/settings` directly in the browser address bar
- **WHEN** the page loads
- **THEN** the SettingsPage SHALL render correctly
- **AND** the sidebar SHALL highlight "設定" as the active item

#### Scenario: Unknown route fallback
- **GIVEN** the user navigates to an undefined route
- **WHEN** the router evaluates the path
- **THEN** it SHALL redirect to `/` (translation workspace)

### Requirement: Translation Wizard Navigation
The translation workspace SHALL implement an interactive 3-step wizard with clickable step navigation.

#### Scenario: Step indicator interactivity
- **GIVEN** the user is on step 2 of the translation wizard
- **WHEN** the user clicks step 1 in the step indicator
- **THEN** the wizard SHALL navigate back to step 1 (upload)
- **AND** previously uploaded files SHALL be preserved

#### Scenario: Step progression rules
- **GIVEN** the user is on step 1
- **WHEN** no files have been uploaded
- **THEN** step 2 SHALL be visually disabled and not clickable
- **AND** the "下一步" button SHALL be disabled

#### Scenario: Step lock during translation
- **GIVEN** a translation job is in progress (step 3)
- **WHEN** the user clicks step 1 or step 2
- **THEN** navigation SHALL be blocked
- **AND** a toast notification SHALL inform the user to cancel or wait for completion

#### Scenario: Completion to new job
- **GIVEN** the translation job has completed on step 3
- **WHEN** the user clicks "開始新翻譯"
- **THEN** the wizard SHALL reset to step 1
- **AND** all state (files, languages, settings) SHALL be cleared

### Requirement: Toast Notification System
The frontend SHALL use a toast notification system to replace all `alert()` calls and provide feedback for user actions.

#### Scenario: Translation completion notification
- **GIVEN** a translation job finishes successfully
- **WHEN** step 3 updates to completed status
- **THEN** a success toast SHALL appear with message "翻譯完成，共 N 個檔案已就緒"
- **AND** it SHALL auto-dismiss after 5 seconds

#### Scenario: Error notification persistence
- **GIVEN** a translation job fails
- **WHEN** step 3 displays error state
- **THEN** an error toast SHALL appear with the error message
- **AND** it SHALL NOT auto-dismiss (requires manual close)

#### Scenario: Term approval notification
- **GIVEN** the user approves a term on `/terms/review`
- **WHEN** the approval API succeeds
- **THEN** a success toast SHALL appear with "術語已核准：{source} → {target}"
- **AND** it SHALL auto-dismiss after 3 seconds

#### Scenario: Ollama offline warning
- **GIVEN** the health check detects Ollama is unreachable
- **WHEN** the status changes from online to offline
- **THEN** a warning toast SHALL appear with "Ollama 服務未回應，請確認已啟動"
- **AND** it SHALL NOT auto-dismiss until Ollama reconnects

### Requirement: Term Review Page
The frontend SHALL provide a dedicated term review page at `/terms/review` with filtering, searching, inline editing, and batch approval.

#### Scenario: Term review list
- **GIVEN** the user navigates to `/terms/review`
- **WHEN** the page renders
- **THEN** it SHALL display unverified terms as cards, each showing: source text, target text, domain, target language, confidence score
- **AND** each card SHALL have "編輯" and "核准" action buttons

#### Scenario: Filter by language and domain
- **GIVEN** the term review page is displayed
- **WHEN** the user selects a target language filter
- **THEN** only terms matching the selected language SHALL be shown
- **AND** the filter SHALL work in combination with domain filter and search

#### Scenario: Inline editing
- **GIVEN** the user clicks "編輯" on a term card
- **WHEN** the edit mode activates
- **THEN** the target text SHALL become an editable input field
- **AND** pressing Enter SHALL save and approve the edited term
- **AND** pressing Escape SHALL cancel the edit

#### Scenario: Batch approval
- **GIVEN** the user clicks "全部核准"
- **WHEN** a confirmation dialog appears and the user confirms
- **THEN** all currently visible (filtered) terms SHALL be approved via API
- **AND** a toast SHALL show the count of approved terms

### Requirement: Settings Page
The frontend SHALL provide a dedicated settings page at `/settings` consolidating all configuration options.

#### Scenario: Settings page sections
- **GIVEN** the user navigates to `/settings`
- **WHEN** the page renders
- **THEN** it SHALL display sections: "系統狀態", "GPU 與記憶體", "翻譯預設值", "PDF 輸出設定", "介面"
- **AND** each section SHALL be a card with clear heading

#### Scenario: System status section
- **GIVEN** the settings page renders
- **WHEN** the system status section loads
- **THEN** it SHALL display Ollama connection status and version from `GET /api/health`
- **AND** available models list
- **AND** cache statistics from `GET /api/cache/stats` with a "清除快取" button
- **AND** clicking "清除快取" SHALL call `DELETE /api/cache` and show a toast confirmation

#### Scenario: Theme toggle
- **GIVEN** the user is on the interface settings section
- **WHEN** the user selects a theme option
- **THEN** three options SHALL be available: "淺色", "暗色", "跟隨系統"
- **AND** selecting "暗色" SHALL set `data-theme="dark"` on `<html>`
- **AND** the preference SHALL persist to localStorage

### Requirement: Translation History Page
The frontend SHALL provide a translation history page at `/history` showing past job records.

#### Scenario: History list display
- **GIVEN** the user navigates to `/history`
- **WHEN** the page renders
- **THEN** it SHALL display past translation jobs from localStorage, sorted newest first
- **AND** each entry SHALL show: job ID (truncated), file count, target languages, status, duration

#### Scenario: History entry creation
- **GIVEN** a translation job completes (success or failure)
- **WHEN** step 3 receives the final status
- **THEN** a history entry SHALL be saved to localStorage
- **AND** the storage SHALL be capped at 50 entries (oldest removed first)

#### Scenario: Empty history state
- **GIVEN** no translation history exists in localStorage
- **WHEN** the history page renders
- **THEN** an EmptyState component SHALL display with message "尚無翻譯紀錄" and a link to start a new translation

### Requirement: Dark Mode Support
The frontend SHALL support light mode, dark mode, and system-preference-following theme switching.

#### Scenario: Dark mode activation
- **GIVEN** the user selects "暗色" in settings
- **WHEN** the theme changes
- **THEN** `<html>` SHALL have `data-theme="dark"` attribute
- **AND** all CSS custom properties SHALL switch to dark mode values
- **AND** all components SHALL render with dark backgrounds and light text

#### Scenario: System preference following
- **GIVEN** the user selects "跟隨系統" in settings
- **WHEN** the OS dark mode preference changes
- **THEN** the theme SHALL automatically switch to match the OS preference

#### Scenario: Theme persistence
- **GIVEN** the user sets theme to "暗色"
- **WHEN** the user closes and reopens the application
- **THEN** the theme SHALL load as "暗色" from localStorage

### Requirement: Internationalization System
The frontend SHALL support UI language switching between Traditional Chinese and English using a lightweight key-value i18n system.

#### Scenario: Default language
- **GIVEN** the application loads for the first time
- **WHEN** no language preference is stored
- **THEN** the UI SHALL render in Traditional Chinese (zh-TW)

#### Scenario: Language switching
- **GIVEN** the user selects "English" in interface settings
- **WHEN** the language changes
- **THEN** all UI labels, buttons, and messages SHALL switch to English
- **AND** the preference SHALL persist to localStorage

#### Scenario: Technical terms preservation
- **GIVEN** the UI is displayed in either language
- **WHEN** technical identifiers appear
- **THEN** Job IDs, VRAM values, model names, and num_ctx SHALL always display in English/numeric format regardless of UI language

### Requirement: Unified API Client
The frontend SHALL use a unified API client module that provides consistent error handling, base URL configuration, and response parsing.

#### Scenario: API error handling
- **GIVEN** any API call returns a non-OK response
- **WHEN** the unified client processes the response
- **THEN** it SHALL parse the response body for a `detail` field
- **AND** throw an Error with the detail message (or status code fallback)

#### Scenario: API module organization
- **GIVEN** the frontend needs to call backend APIs
- **WHEN** developers import API functions
- **THEN** functions SHALL be organized by domain: `api/jobs.js` (translation), `api/terms.js` (term DB), `api/system.js` (health, cache, stats), `api/config.js` (profiles, model config)
