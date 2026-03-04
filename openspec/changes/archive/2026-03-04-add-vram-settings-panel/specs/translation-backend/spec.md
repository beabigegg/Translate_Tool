## ADDED Requirements

### Requirement: VRAM Metadata Configuration
The system SHALL provide per-model-type VRAM metadata for frontend VRAM estimation.

#### Scenario: VRAM metadata available per model type
- **GIVEN** the backend configuration is loaded
- **AND** `OLLAMA_NUM_CTX` environment variable is not set
- **WHEN** VRAM metadata is queried
- **THEN** each model type SHALL have `model_size_gb`, `kv_per_1k_ctx_gb`, `default_num_ctx`, `min_num_ctx`, and `max_num_ctx` values
- **AND** general type SHALL report `model_size_gb=3.5`, `kv_per_1k_ctx_gb=0.35`, `default_num_ctx=4096`
- **AND** translation type SHALL report `model_size_gb=5.7`, `kv_per_1k_ctx_gb=0.22`, `default_num_ctx=3072`

#### Scenario: VRAM metadata reflects OLLAMA_NUM_CTX override
- **GIVEN** the backend configuration is loaded
- **AND** `OLLAMA_NUM_CTX` environment variable is set (e.g., `5120`)
- **WHEN** VRAM metadata is queried
- **THEN** `default_num_ctx` for all model types SHALL reflect the overridden value
- **AND** `model_size_gb` and `kv_per_1k_ctx_gb` SHALL remain unchanged

### Requirement: Model Config API Endpoint
The system SHALL expose a REST endpoint to retrieve per-model-type VRAM and configuration metadata.

#### Scenario: Get model config
- **GIVEN** the backend is running
- **WHEN** a GET request is made to `/api/model-config`
- **THEN** the response SHALL be a JSON array of objects, each with `model_type`, `model_size_gb`, `kv_per_1k_ctx_gb`, `default_num_ctx`, `min_num_ctx`, `max_num_ctx`
- **AND** the response content type SHALL be `application/json`

### Requirement: Per-Job num_ctx Override
The system SHALL accept an optional `num_ctx` parameter in job creation that overrides the per-model-type default for that job only.

#### Scenario: Job with num_ctx override
- **GIVEN** a job creation request includes `num_ctx=2048`
- **WHEN** the translation job executes
- **THEN** the OllamaClient SHALL use `num_ctx=2048` in its options payload
- **AND** the `[CONFIG]` log line SHALL include `num_ctx=2048 (override)`

#### Scenario: Job without num_ctx override
- **GIVEN** a job creation request omits `num_ctx`
- **WHEN** the translation job executes
- **THEN** the OllamaClient SHALL use the per-model-type default `num_ctx` from `MODEL_TYPE_OPTIONS`

#### Scenario: num_ctx override threaded through pipeline
- **GIVEN** a job with `num_ctx=2048` is created
- **WHEN** the job is processed
- **THEN** the `num_ctx` value SHALL be passed from routes through job_manager, orchestrator, to OllamaClient
- **AND** `_build_options()` SHALL use the override value instead of the model-type default

#### Scenario: num_ctx override out of bounds rejected
- **GIVEN** a job creation request includes `num_ctx` outside the resolved model type's `[min_num_ctx, max_num_ctx]` range
- **WHEN** the POST /api/jobs request is processed
- **THEN** the system SHALL return HTTP 422 with an error message indicating the allowed range
- **AND** the job SHALL NOT be created

#### Scenario: num_ctx override must be a positive integer
- **GIVEN** a job creation request includes a valid `num_ctx` value
- **WHEN** the value is applied
- **THEN** the system SHALL accept only positive integer values
