## MODIFIED Requirements

### Requirement: Profile-Driven Translation Backend
The system SHALL select the translation model and prompt strategy based on the resolved profile. The default model SHALL be `qwen3.5:4b`. The frontend SHALL only send a `profile` identifier; the backend resolves the profile to obtain the model name, model type, and system prompt. The `POST /api/jobs` endpoint SHALL NOT accept a `model` parameter.

Before Phase 1 begins, the system SHALL execute Phase 0 (term extraction) in full: Qwen 9B extracts terms from the entire document, unknown terms are translated by the same Qwen 9B instance, results are stored in the Term DB, and Qwen 9B is unloaded. Phase 1 SHALL NOT start until Phase 0 is complete.

When `mode=extraction_only` is submitted, the pipeline SHALL stop after Phase 0 and SHALL NOT proceed to Phase 1 or Phase 2.

#### Scenario: Successful translation with Qwen 3.5
- **GIVEN** Ollama service is running with `qwen3.5:4b` model loaded
- **WHEN** user submits text for translation with a selected profile
- **THEN** the system SHALL send the profile's system prompt via the Ollama `system` field
- **AND** send the source text with language direction via the `prompt` field
- **AND** return the translated text without additional commentary

#### Scenario: System prompt separation
- **GIVEN** a translation profile with a non-empty system prompt is selected
- **WHEN** the translation request is processed
- **THEN** the system SHALL include `"system": "<profile_system_prompt>"` in the Ollama API payload
- **AND** the `prompt` field SHALL contain only the language direction and source text

#### Scenario: Phase 0 completes before Phase 1 starts
- **GIVEN** a document is submitted for translation
- **WHEN** the pipeline is initiated
- **THEN** Phase 0 term extraction SHALL run to completion
- **AND** Qwen 9B SHALL be unloaded after Phase 0
- **AND** Phase 1 Primary Model SHALL only load after Phase 0 is confirmed complete

#### Scenario: Phase 0 failure does not abort translation
- **GIVEN** Qwen 9B fails or produces unparseable output during Phase 0
- **WHEN** the pipeline continues
- **THEN** Phase 1 SHALL proceed using only the terms already present in the local Term DB
- **AND** a warning SHALL be logged indicating the failure

## ADDED Requirements

### Requirement: Extraction-Only Job Mode
The `POST /api/jobs` endpoint SHALL accept an optional `mode` parameter. When `mode=extraction_only`, the backend SHALL execute Phase 0 only and return a summary of extracted and stored terms without running Phase 1 or Phase 2.

#### Scenario: Extraction-only job created
- **GIVEN** a POST /api/jobs request with `mode=extraction_only`
- **WHEN** the job is processed
- **THEN** Phase 0 SHALL run to completion (extract + translate unknown terms + write to DB + unload Qwen 9B)
- **AND** the job SHALL complete without executing Phase 1 or Phase 2
- **AND** no translated output file SHALL be produced

#### Scenario: Extraction-only job result
- **GIVEN** an extraction-only job has completed
- **WHEN** the job status is polled
- **THEN** the response SHALL include a `term_summary` object with: `extracted` (total candidates), `skipped` (already in DB), `added` (newly stored)

#### Scenario: Default mode is translation
- **GIVEN** a POST /api/jobs request with no `mode` field
- **WHEN** the job is processed
- **THEN** the pipeline SHALL proceed with Phase 0 → Phase 1 → Phase 2 as normal

### Requirement: Term Database API Endpoints
The backend SHALL expose REST endpoints for term database statistics, export, and import.

#### Scenario: Get term database statistics
- **GIVEN** the backend is running
- **WHEN** a GET request is made to `/api/terms/stats`
- **THEN** the response SHALL be JSON with: `total` count, `by_target_lang` object, `by_domain` object

#### Scenario: Export term database
- **GIVEN** the backend is running
- **WHEN** a GET request is made to `/api/terms/export?format=json` (or `csv` or `xlsx`)
- **THEN** the backend SHALL return the file as a download with appropriate Content-Type and Content-Disposition headers

#### Scenario: Import term database
- **GIVEN** the backend is running
- **WHEN** a POST request is made to `/api/terms/import?strategy=skip` with a JSON or CSV file
- **THEN** the backend SHALL process the import with the specified conflict strategy
- **AND** return JSON with: `inserted`, `skipped`, `overwritten` counts
