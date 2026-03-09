# frontend-ui Specification

## Purpose
TBD - created by archiving change add-translation-profiles. Update Purpose after archive.
## Requirements
### Requirement: Translation Profile Selector
The frontend SHALL display a profile selector that allows users to choose a translation profile before submitting a job.

#### Scenario: Profile selector visibility
- **GIVEN** the user is on the configuration step
- **WHEN** the page renders
- **THEN** the profile selector SHALL be always visible in the right column above the Advanced Settings section
- **AND** SHALL NOT be hidden inside the collapsible Advanced Settings

#### Scenario: Profile selector rendering
- **GIVEN** the backend returns a list of profiles from `GET /api/profiles`
- **WHEN** the profile selector renders
- **THEN** each profile SHALL be displayed as a radio button with its `name` and `description`
- **AND** the `general` profile SHALL be selected by default

#### Scenario: Profile selection persists to job submission
- **GIVEN** the user selects the "semiconductor" profile
- **WHEN** the user clicks "Start Translation"
- **THEN** the form data SHALL include `profile=semiconductor`
- **AND** SHALL NOT include a hardcoded `model` field

#### Scenario: Profile fetch failure fallback
- **GIVEN** the `GET /api/profiles` request fails
- **WHEN** the frontend handles the error
- **THEN** a fallback profile entry for "general" SHALL be shown
- **AND** the user SHALL still be able to submit translation jobs

### Requirement: Remove Hardcoded Model
The frontend SHALL no longer hardcode a specific model name. Model selection SHALL be derived from the selected profile on the backend.

#### Scenario: No hardcoded model in frontend
- **GIVEN** the App component initializes
- **WHEN** state variables are declared
- **THEN** there SHALL be no hardcoded model string (e.g., `"translategemma:12b"`)
- **AND** the `model` form field SHALL be replaced by `profile`

### Requirement: Frontend State Management for Profiles
The App component SHALL manage profile state alongside existing state variables, following the same patterns used for other configuration state.

#### Scenario: Profile state initialization
- **GIVEN** the App component mounts
- **WHEN** initial state is set
- **THEN** the component SHALL declare `profiles` state (array of profile objects, initially empty) and `selectedProfile` state (string, initially `"general"`)
- **AND** the hardcoded `const model = "translategemma:12b"` line SHALL be removed entirely

#### Scenario: Profile data fetching on mount
- **GIVEN** the App component mounts
- **WHEN** the initial `useEffect` fires
- **THEN** it SHALL call `fetchProfiles()` from `api.js`
- **AND** on success, store the profiles array in state and keep `selectedProfile` as `"general"`
- **AND** on failure, set profiles to the fallback array `[{id: "general", name: "通用翻譯", description: "General translation"}]` and log the error to console

#### Scenario: Profile state does not affect other state
- **GIVEN** the user changes the selected profile
- **WHEN** the profile state updates
- **THEN** no other state variables (files, selectedTargets, srcLang, etc.) SHALL be affected

### Requirement: Frontend API Integration for Profiles
The `api.js` module SHALL export a `fetchProfiles()` function for retrieving available profiles.

#### Scenario: fetchProfiles function
- **GIVEN** the api.js module
- **WHEN** `fetchProfiles()` is called
- **THEN** it SHALL send a GET request to `/api/profiles`
- **AND** return the parsed JSON response, which is a bare array of `{id, name, description, model_type}` objects (no wrapper object)
- **AND** throw an Error with message "Failed to load profiles" on non-OK response

#### Scenario: Form submission with profile and optional num_ctx
- **GIVEN** the user clicks "Start Translation"
- **WHEN** `handleStart` builds the FormData
- **THEN** it SHALL append `form.append("profile", selectedProfile)`
- **AND** if `numCtxOverride` is not null, it SHALL append `form.append("num_ctx", numCtxOverride)`
- **AND** all other form fields SHALL remain unchanged

### Requirement: Profile Selector UI Component Structure
The profile selector SHALL be rendered as a dedicated card in the right column, using existing CSS design system patterns.

#### Scenario: Card structure and position
- **GIVEN** the right column (`column-right`) renders
- **WHEN** the profile selector card is displayed
- **THEN** it SHALL appear as a `<section className="card">` element
- **AND** it SHALL be the first card in the right column, rendered BEFORE the Advanced Settings card
- **AND** it SHALL have a non-collapsible card header with title "Translation Profile" (翻譯模式)

#### Scenario: Radio button list using existing CSS patterns
- **GIVEN** the profiles array has been loaded
- **WHEN** the profile options render
- **THEN** each profile SHALL be rendered inside a `.setting-group` containing a `.radio-group`
- **AND** each profile option SHALL use the existing `.radio-option` CSS class with `.selected` when active
- **AND** each radio button label SHALL display the profile `name` in `<strong>` and `description` in `<small>`, wrapped in a `.radio-label` div
- **AND** the selected profile's `.radio-option` SHALL have the `.selected` class applied

#### Scenario: Profile selector interaction
- **GIVEN** the profile selector is displayed with "general" selected
- **WHEN** the user clicks a different profile radio button (e.g., "semiconductor")
- **THEN** `selectedProfile` state SHALL update to `"semiconductor"`
- **AND** the clicked option SHALL gain the `.selected` class
- **AND** the previously selected option SHALL lose the `.selected` class

#### Scenario: Profile selector during translation
- **GIVEN** a translation job is in progress (step 2: Translate)
- **WHEN** the right column renders
- **THEN** the profile selector card SHALL still be visible but all radio buttons SHALL be disabled
- **AND** the user SHALL NOT be able to change the profile while a job is running

### Requirement: Source Language Auto-Detect Default
The frontend SHALL provide an "Auto-detect" option for source language selection and make it the default.

#### Scenario: Auto-detect as default source language
- **GIVEN** the App component mounts
- **WHEN** source language state is initialized
- **THEN** `srcLang` SHALL default to `"auto"` instead of `"English"`
- **AND** the source language selector SHALL display "Auto-detect (自動偵測)" as the first option

#### Scenario: Explicit source language selection
- **GIVEN** the user selects "English" from the source language selector
- **WHEN** the form is submitted
- **THEN** the `src_lang` form field SHALL be `"English"` (not `"auto"`)

#### Scenario: Auto-detect in form submission
- **GIVEN** the user leaves source language as "Auto-detect"
- **WHEN** the form is submitted
- **THEN** the `src_lang` form field SHALL be `"auto"`

#### Scenario: Reset restores auto-detect default
- **GIVEN** the user previously selected "English" as source language
- **WHEN** the user clicks "Translate More" (handleReset)
- **THEN** `srcLang` SHALL be reset to `"auto"`

### Requirement: handleReset Clears Profile Selection
The reset flow SHALL restore profile selection to its default state.

#### Scenario: Reset restores default profile
- **GIVEN** the user had selected "semiconductor" profile and completed a translation
- **WHEN** the user clicks "Translate More" (handleReset)
- **THEN** `selectedProfile` SHALL be reset to `"general"`
- **AND** the profile selector SHALL show "general" as selected

### Requirement: VRAM Calculator Panel
The frontend SHALL display a VRAM calculator inside the Advanced Settings card that shows estimated GPU memory usage for the selected profile and allows per-job `num_ctx` adjustment.

#### Scenario: VRAM panel visibility
- **GIVEN** the user expands the Advanced Settings card
- **WHEN** the settings content renders
- **THEN** a "VRAM 試算" (VRAM Estimate) setting group SHALL appear below the PDF settings
- **AND** it SHALL display: GPU capacity selector, num_ctx slider, estimated VRAM usage bar

#### Scenario: GPU capacity selector
- **GIVEN** the VRAM panel is displayed
- **WHEN** the user selects a GPU capacity value
- **THEN** the available options SHALL include common VRAM sizes (6, 8, 10, 12, 16, 24 GB)
- **AND** the default SHALL be 8 GB
- **AND** the selected value SHALL be persisted to localStorage

#### Scenario: num_ctx slider
- **GIVEN** the VRAM panel is displayed
- **WHEN** the user adjusts the num_ctx slider
- **THEN** the slider range SHALL be bound by the selected profile's `min_num_ctx` and `max_num_ctx`
- **AND** the estimated VRAM SHALL recalculate in real time
- **AND** the current num_ctx value SHALL be displayed next to the slider

#### Scenario: VRAM usage bar display
- **GIVEN** a profile is selected and num_ctx is set
- **WHEN** the VRAM bar renders
- **THEN** it SHALL show estimated total VRAM as `model_size_gb + (num_ctx / 1024) * kv_per_1k_ctx_gb`
- **AND** display the breakdown: "Model: X.X GB + KV Cache: X.X GB = Total: X.X GB"
- **AND** the bar color SHALL be green when usage < 75% of GPU capacity, yellow when 75-90%, red when > 90%

#### Scenario: VRAM panel resets on profile change
- **GIVEN** the user changes the selected profile
- **WHEN** the profile state updates
- **THEN** the num_ctx slider SHALL reset to the new profile's `default_num_ctx`
- **AND** the VRAM bar SHALL recalculate with the new model's metadata

#### Scenario: VRAM panel disabled during translation
- **GIVEN** a translation job is in progress
- **WHEN** the VRAM panel renders
- **THEN** the num_ctx slider and GPU capacity selector SHALL be disabled

### Requirement: Frontend Model Config API Integration
The `api.js` module SHALL export a `fetchModelConfig()` function for retrieving per-model-type VRAM and configuration metadata.

#### Scenario: fetchModelConfig function
- **GIVEN** the api.js module
- **WHEN** `fetchModelConfig()` is called
- **THEN** it SHALL send a GET request to `/api/model-config`
- **AND** return the parsed JSON response (array of model config objects)
- **AND** on failure, return a hardcoded fallback array with default values for both model types

#### Scenario: Model config fetched on mount
- **GIVEN** the App component mounts
- **WHEN** the initial `useEffect` fires
- **THEN** it SHALL call `fetchModelConfig()` alongside `fetchProfiles()`
- **AND** store the result in `modelConfig` state

### Requirement: Extraction-Only Mode Trigger
The frontend SHALL provide a mode toggle that allows the user to run Phase 0 (term extraction) without proceeding to translation. The toggle SHALL be visible on the configuration step alongside the existing "Start Translation" button.

#### Scenario: Mode toggle visibility
- **GIVEN** the user is on the configuration step (step 1)
- **WHEN** the page renders
- **THEN** two mode options SHALL be displayed: "翻譯" (Translate) and "僅萃取術語" (Extract Terms Only)
- **AND** "翻譯" SHALL be selected by default

#### Scenario: Extraction-only mode submission
- **GIVEN** the user selects "僅萃取術語" mode and clicks the action button
- **WHEN** the form is submitted
- **THEN** the request SHALL include `mode=extraction_only` in the form data
- **AND** the action button label SHALL read "開始萃取" instead of "開始翻譯"

#### Scenario: Extraction-only mode skips translation settings
- **GIVEN** the user selects "僅萃取術語" mode
- **WHEN** the mode is active
- **THEN** the profile selector and VRAM calculator SHALL still be visible but non-critical for this mode
- **AND** only file upload and target language selection are required

---

### Requirement: Extraction Progress and Result Display
The frontend SHALL display progress during Phase 0 execution and show the extracted terms upon completion when running in extraction-only mode.

#### Scenario: Extraction progress display
- **GIVEN** an extraction-only job is running
- **WHEN** the job emits progress events
- **THEN** the UI SHALL display a progress bar or status message indicating extraction progress (e.g., "正在萃取術語… 第 N / M 段")
- **AND** the UI SHALL indicate when Qwen 9B is translating extracted terms

#### Scenario: Extraction result summary
- **GIVEN** an extraction-only job has completed
- **WHEN** the result is displayed
- **THEN** the UI SHALL show: total terms extracted, terms already in DB (skipped), new terms added
- **AND** a "匯出結果" button SHALL be available to export the newly added terms

---

### Requirement: Term Database Management Panel
The frontend SHALL provide a term database management panel accessible from the main UI. The panel SHALL allow users to view database statistics, export, and import the term database.

#### Scenario: Panel accessibility
- **GIVEN** the user is on any step of the main UI
- **WHEN** the term database panel trigger is visible
- **THEN** a "術語庫" (Term Database) button or tab SHALL be visible in the UI
- **AND** clicking it SHALL open the management panel

#### Scenario: Database statistics display
- **GIVEN** the term database panel is open
- **WHEN** statistics are loaded from `GET /api/terms/stats`
- **THEN** the panel SHALL display: total term count, breakdown by target language, breakdown by domain

#### Scenario: Export term database
- **GIVEN** the term database panel is open
- **WHEN** the user clicks "匯出"
- **THEN** a format selector SHALL appear with options: JSON, CSV, XLSX
- **AND** selecting a format SHALL trigger a download via `GET /api/terms/export?format=<json|csv|xlsx>`

#### Scenario: Import term database
- **GIVEN** the term database panel is open
- **WHEN** the user clicks "匯入"
- **THEN** a file picker SHALL open accepting `.json` and `.csv` files
- **AND** a conflict strategy selector SHALL appear with options: 保留現有 (skip), 覆蓋 (overwrite), 依信心值合併 (merge)
- **AND** confirming SHALL POST the file to `POST /api/terms/import?strategy=<skip|overwrite|merge>`

#### Scenario: Import result feedback
- **GIVEN** an import has completed
- **WHEN** the backend responds
- **THEN** the panel SHALL display: "新增 N 筆、略過 N 筆、覆蓋 N 筆"
- **AND** the statistics display SHALL refresh automatically

