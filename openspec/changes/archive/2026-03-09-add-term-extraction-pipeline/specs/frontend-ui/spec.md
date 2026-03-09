## ADDED Requirements

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
