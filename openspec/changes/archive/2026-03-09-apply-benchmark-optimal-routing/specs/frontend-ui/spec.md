## MODIFIED Requirements

### Requirement: Translation Profile Selector
The frontend SHALL move the profile selector into the Advanced Settings section as an override control, with auto-routing as the default behavior.

#### Scenario: Auto-routing as default
- **GIVEN** the user is on the configuration step
- **WHEN** the page renders
- **THEN** the profile selector SHALL NOT be visible in the main view
- **AND** a hint text SHALL display: "系統自動選擇最佳翻譯模型" (System auto-selects optimal model)

#### Scenario: Profile override in Advanced Settings
- **GIVEN** the user expands Advanced Settings
- **WHEN** the settings content renders
- **THEN** a profile override dropdown SHALL appear with options: "自動 (Auto)" (default) and all available profiles
- **AND** selecting a specific profile SHALL override the automatic routing

#### Scenario: Profile selection persists to job submission
- **GIVEN** the user selects a specific profile override (e.g., "semiconductor")
- **WHEN** the user clicks "Start Translation"
- **THEN** the form data SHALL include `profile=semiconductor`

#### Scenario: Auto mode in form submission
- **GIVEN** the user leaves the profile as "自動 (Auto)"
- **WHEN** the user clicks "Start Translation"
- **THEN** the form data SHALL NOT include a `profile` field (or include `profile=auto`)

#### Scenario: Profile fetch failure fallback
- **GIVEN** the `GET /api/profiles` request fails
- **WHEN** the frontend handles the error
- **THEN** the auto-routing mode SHALL still function
- **AND** the profile override dropdown SHALL show only "自動 (Auto)"

### Requirement: Simplified Target Language Selection
The frontend SHALL display a compact list of commonly-used target languages as a checkbox grid, replacing the grouped language selector with search.

#### Scenario: Available target languages
- **GIVEN** the user is on the configuration step
- **WHEN** the target language section renders
- **THEN** the following 8 languages SHALL be displayed: English, Vietnamese, Thai, Japanese, Korean, Indonesian, Traditional Chinese, Simplified Chinese
- **AND** each language SHALL show both English and Chinese labels (e.g., "English 英語")

#### Scenario: Target language selection
- **GIVEN** the target language grid is displayed
- **WHEN** the user clicks a language checkbox
- **THEN** the language SHALL be toggled in the selected targets list
- **AND** at least one target language SHALL always remain selected

#### Scenario: Default target languages
- **GIVEN** the App component mounts
- **WHEN** target language state is initialized
- **THEN** "English" and "Vietnamese" SHALL be selected by default

#### Scenario: Output order preserved
- **GIVEN** multiple target languages are selected
- **WHEN** the form is submitted
- **THEN** the order SHALL match the order in which they were selected

### Requirement: Source Language Auto-Detect Default
The frontend SHALL default source language to Auto-detect and move the source language selector into Advanced Settings.

#### Scenario: Auto-detect as default source language
- **GIVEN** the App component mounts
- **WHEN** source language state is initialized
- **THEN** `srcLang` SHALL default to `"auto"`
- **AND** the source language selector SHALL NOT appear in the main view

#### Scenario: Source language override in Advanced Settings
- **GIVEN** the user expands Advanced Settings
- **WHEN** the settings content renders
- **THEN** a source language selector SHALL appear allowing the user to change from Auto-detect to a specific language

#### Scenario: Reset restores auto-detect default
- **GIVEN** the user previously selected a specific source language
- **WHEN** the user clicks "New Translation" (handleReset)
- **THEN** `srcLang` SHALL be reset to `"auto"`

### Requirement: Two-Column Layout
The frontend SHALL use a two-column layout for the main content area instead of three columns.

#### Scenario: Left column content
- **GIVEN** the main content area renders
- **WHEN** the left column is displayed
- **THEN** it SHALL contain: the file upload card and the target language checkbox grid

#### Scenario: Right column content
- **GIVEN** the main content area renders
- **WHEN** the right column is displayed
- **THEN** it SHALL contain: the translation status card and the Advanced Settings card (collapsed by default)

#### Scenario: Advanced Settings content
- **GIVEN** the user expands Advanced Settings
- **WHEN** the settings content renders
- **THEN** it SHALL contain (in order): profile override dropdown, source language selector, PDF output format, PDF layout mode, VRAM calculator, header translation toggle

### Requirement: Route Info Display
The frontend SHALL display the auto-selected model information when targets are selected.

#### Scenario: Show routing info for selected targets
- **GIVEN** the user has selected target languages and auto-routing is active
- **WHEN** the routing info is fetched from `/api/route-info`
- **THEN** a subtle label SHALL display the model name that will be used (e.g., "使用模型: HY-MT1.5-7B")

#### Scenario: Routing info hidden when profile override is active
- **GIVEN** the user has selected a specific profile override in Advanced Settings
- **WHEN** the route info area renders
- **THEN** the auto-routing label SHALL be hidden
- **AND** the selected profile name SHALL be displayed instead

### Requirement: handleReset Clears Profile Selection
The reset flow SHALL restore profile selection to its default state.

#### Scenario: Reset restores auto-routing
- **GIVEN** the user had selected a profile override and completed a translation
- **WHEN** the user clicks "New Translation" (handleReset)
- **THEN** the profile override SHALL be reset to "自動 (Auto)"
- **AND** auto-routing SHALL be re-enabled

## REMOVED Requirements

### Requirement: Remove Hardcoded Model
**Reason**: Superseded by auto-routing. The original requirement prohibited hardcoded model names; auto-routing now handles model selection dynamically. The intent is fully covered by the new "Language-Based Model Routing" requirement in the `model-routing` spec.
**Migration**: No migration needed; the behavior is preserved through the routing table.
