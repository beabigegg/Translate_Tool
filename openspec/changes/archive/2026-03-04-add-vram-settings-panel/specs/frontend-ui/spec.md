## ADDED Requirements

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

## MODIFIED Requirements

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
