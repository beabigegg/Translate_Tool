## MODIFIED Requirements

### Requirement: Web Frontend UI
The system SHALL provide a local web UI for translation workflows.

#### Scenario: Upload and start translation
- **GIVEN** the user opens the web UI
- **WHEN** the user uploads files and selects target languages
- **THEN** the system starts a translation job
- **AND** displays progress and logs

#### Scenario: Language ordering
- **WHEN** the user reorders target languages in the UI
- **THEN** the system preserves the chosen order for output

#### Scenario: Update settings
- **WHEN** the user changes batch size, timeout settings, or num_ctx override
- **THEN** the system applies the settings to new jobs

#### Scenario: Stop job
- **WHEN** the user clicks Stop
- **THEN** the system requests job cancellation
- **AND** displays the stopped status

#### Scenario: Download results
- **WHEN** a job completes
- **THEN** the UI offers the output archive for download

#### Scenario: Profile grouped by model type
- **WHEN** the profile list is displayed in the UI
- **THEN** profiles SHALL be grouped into two sections by model_type
- **AND** general-purpose profiles are shown under a "通用AI翻譯 (General AI)" heading
- **AND** translation-dedicated profiles are shown under a "專業翻譯引擎 (Dedicated Translation)" heading

#### Scenario: VRAM calculator in advanced settings
- **WHEN** the user expands Advanced Settings
- **THEN** a VRAM calculator panel SHALL be displayed below PDF settings
- **AND** it SHALL show estimated VRAM usage based on the selected profile and num_ctx value

### Requirement: Web API Service
The system SHALL provide a local HTTP API for translation jobs and artifacts.

#### Scenario: Upload creates a job
- **GIVEN** a user uploads one or more supported files with target settings
- **WHEN** the API receives the multipart upload
- **THEN** the system stores files in a job workspace
- **AND** returns a job identifier

#### Scenario: Upload creates a job with num_ctx override
- **GIVEN** a user uploads files with an optional `num_ctx` parameter
- **WHEN** the API receives the multipart upload
- **THEN** the system passes the `num_ctx` override through the pipeline
- **AND** the translation job uses the overridden value instead of the model-type default

#### Scenario: Job status query
- **WHEN** the client requests job status
- **THEN** the system returns state and progress counts
- **AND** includes error details when a job fails

#### Scenario: Log stream
- **WHEN** the client opens the log stream endpoint
- **THEN** the system streams log lines as they are produced
- **AND** streaming does not block translation work

#### Scenario: Download results
- **WHEN** a job completes successfully
- **THEN** the system provides a downloadable archive of outputs
- **AND** results remain available until cleaned

#### Scenario: Cancel job
- **WHEN** the client requests job cancellation
- **THEN** the system signals stop and completes the current file
- **AND** the job status reports "stopped"

#### Scenario: Model config endpoint
- **WHEN** the client requests model configuration via GET /api/model-config
- **THEN** the system returns per-model-type VRAM metadata and num_ctx defaults
