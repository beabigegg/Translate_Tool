## ADDED Requirements

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
- **AND** return the parsed JSON response, which is a bare array of `{id, name, description}` objects (no wrapper object)
- **AND** throw an Error with message "Failed to load profiles" on non-OK response

#### Scenario: Form submission with profile
- **GIVEN** the user clicks "Start Translation"
- **WHEN** `handleStart` builds the FormData
- **THEN** it SHALL append `form.append("profile", selectedProfile)` instead of `form.append("model", model)`
- **AND** all other form fields (files, targets, src_lang, include_headers, pdf_output_format, pdf_layout_mode) SHALL remain unchanged

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
