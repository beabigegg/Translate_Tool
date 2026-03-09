# Translation Backend Specification

## Purpose
Defines the translation backend configuration and behavior, including support for local TranslateGemma model via Ollama service, health checks, and timeout settings.
## Requirements
### Requirement: Ollama Health Check Enhancement
The system SHALL verify Ollama service availability and model readiness before translation.

#### Scenario: Ollama service healthy
- **GIVEN** Ollama service is running on localhost:11434
- **WHEN** health check is performed
- **THEN** the system SHALL confirm service availability
- **AND** list available models including translategemma:12b

#### Scenario: Ollama service unavailable
- **GIVEN** Ollama service is not running
- **WHEN** health check is performed
- **THEN** the system SHALL display an error message indicating Ollama is not accessible
- **AND** suggest user to start Ollama service

### Requirement: Extended Timeout for Local Inference
The system SHALL use extended timeout settings for local model inference.

#### Scenario: Long text translation timeout
- **GIVEN** a document with paragraphs exceeding 500 characters
- **WHEN** translating via TranslateGemma locally
- **THEN** the system SHALL allow up to 180 seconds for API response
- **AND** not timeout prematurely during model inference

### Requirement: Default Model Selection
The system SHALL default to `qwen3.5:4b` as the general-purpose model. Translation-dedicated models (e.g., HY-MT1.5-7B) SHALL be available as an alternative selection via the profile system.

#### Scenario: Application startup with Ollama available
- **GIVEN** Ollama service is running
- **WHEN** the application starts
- **THEN** the system SHALL use `qwen3.5:4b` as the default model via the general profile
- **AND** the profile list SHALL include both general and translation-dedicated profiles

#### Scenario: Application startup without Ollama
- **GIVEN** Ollama service is not running
- **WHEN** the application starts
- **THEN** the system SHALL display a warning that Ollama is not available
- **AND** suggest user to start Ollama service

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

### Requirement: 8GB VRAM Runtime Tuning Defaults
The system SHALL provide per-model-type runtime defaults tuned for RTX 4060 8GB-class environments. Model-level parameters (`num_ctx`, `num_gpu`, `kv_cache_type`) SHALL be managed in backend `config.py` via `MODEL_TYPE_OPTIONS`, not in the shell startup script.

#### Scenario: Per-model-type num_ctx defaults
- **GIVEN** no overriding environment variables are set
- **WHEN** backend configuration is loaded
- **THEN** general-purpose model type SHALL use `num_ctx=4096`
- **AND** translation-dedicated model type SHALL use `num_ctx=3072`
- **AND** both values SHALL fit within 8GB VRAM budget with their respective model sizes

#### Scenario: Global GPU defaults in backend config
- **GIVEN** no overriding environment variables are set
- **WHEN** backend configuration is loaded
- **THEN** `OLLAMA_NUM_GPU` default SHALL be `99`
- **AND** `OLLAMA_KV_CACHE_TYPE` default SHALL be `q8_0`

#### Scenario: Shell script retains transport-level defaults only
- **GIVEN** `translate_tool.sh start` is used
- **WHEN** runtime environment variables are unset
- **THEN** the script SHALL set defaults for transport-level settings: `TRANSLATE_CONNECT_TIMEOUT=15`, `TRANSLATE_READ_TIMEOUT=360`
- **AND** the script SHALL NOT set model-level settings (`OLLAMA_NUM_CTX`, `OLLAMA_NUM_GPU`, `OLLAMA_KV_CACHE_TYPE`)

#### Scenario: Environment variable override honored
- **GIVEN** a user sets `OLLAMA_NUM_CTX=5120` in their environment
- **WHEN** backend configuration is loaded
- **THEN** the user-provided value SHALL override the per-model-type default
- **AND** the override SHALL apply to all model types

#### Scenario: Fallback when near-limit context is unstable
- **GIVEN** an 8GB GPU environment experiences instability or severe slowdown
- **WHEN** runtime tuning is adjusted
- **THEN** lowering `num_ctx` in the per-model-type config SHALL be the documented first-line fallback
- **AND** translation behavior SHALL remain functionally correct through existing chunking/retry paths

### Requirement: Two-Tier Prompt Architecture
The system SHALL separate translation prompts into a system prompt (static per job, domain instructions) and a user prompt (dynamic per request, language direction + source text).

#### Scenario: User prompt for single translation (system prompt path)
- **GIVEN** an OllamaClient with a system_prompt set
- **WHEN** `translate_once` builds the user prompt
- **THEN** the prompt SHALL contain a language direction line (e.g., "Translate from English to Traditional Chinese:")
- **AND** SHALL contain the source text
- **AND** SHALL NOT contain domain instructions or persona definitions (those belong in the system prompt)

#### Scenario: User prompt for merged-context batch translation
- **GIVEN** an OllamaClient with a system_prompt set
- **WHEN** `translate_merged_paragraphs` in `translation_helpers.py` builds the augmented prompt
- **THEN** the prompt SHALL prepend marker preservation instructions ("Keep the <<<SEG_N>>> markers")
- **AND** the system prompt SHALL already contain output format rules, so the user prompt focuses on the specific request

#### Scenario: User prompt for `translate_batch` (system prompt path)
- **GIVEN** an OllamaClient with a system_prompt set
- **WHEN** `translate_batch` builds the batch prompt
- **THEN** the prompt SHALL contain segments with `<<<SEG_N>>>` markers, language direction, and output format instructions
- **AND** SHALL NOT repeat the domain persona or terminology (those live in the system prompt)

### Requirement: Payload Construction Helper
The system SHALL use a centralized helper method to construct Ollama API payloads, ensuring consistent inclusion of model, options, and optional system prompt across all translation paths (single, batch, chunked, retry).

#### Scenario: Payload with system prompt
- **GIVEN** an OllamaClient instance with a system_prompt set
- **WHEN** any translation method builds a payload
- **THEN** the payload SHALL include `"system"` key with the system prompt value

#### Scenario: Payload without system prompt
- **GIVEN** an OllamaClient instance without a system_prompt
- **WHEN** any translation method builds a payload
- **THEN** the payload SHALL NOT include a `"system"` key

#### Scenario: All translation paths use the helper
- **GIVEN** the methods `translate_once`, `_translate_chunked`, `_translate_with_extended_retry`, and `translate_batch`
- **WHEN** any of them constructs an Ollama API payload
- **THEN** they SHALL use `_build_payload(prompt)` instead of inline dict construction

### Requirement: Profile-Aware Cache Keys
The translation cache SHALL differentiate entries by profile to prevent cross-profile cache contamination.

#### Scenario: Cache key includes profile identifier
- **GIVEN** translations performed with profile "semiconductor"
- **WHEN** the same text is later requested with profile "legal"
- **THEN** the cache SHALL treat these as distinct entries (cache miss for "legal")

#### Scenario: Cache key format
- **GIVEN** model "qwen3.5:9b" and profile_id "semiconductor"
- **WHEN** the cache model key is computed
- **THEN** the key SHALL be "qwen3.5:9b::semiconductor"

#### Scenario: No profile defaults to model-only key
- **GIVEN** no profile_id is set on the client
- **WHEN** the cache model key is computed
- **THEN** the key SHALL be the model name only (e.g., "qwen3.5:9b")

### Requirement: Cache Clear Compatibility with Composite Keys
The `TranslationCache.clear(model=...)` method SHALL support clearing all profile variants of a given model without accidentally deleting entries for unrelated models that share a name prefix.

#### Scenario: Clear all entries for a model regardless of profile
- **GIVEN** cache contains entries with model keys "qwen3.5:9b", "qwen3.5:9b::semiconductor", and "qwen3.5:9b::legal"
- **WHEN** `clear(model="qwen3.5:9b")` is called
- **THEN** all three entries SHALL be deleted
- **AND** the query SHALL use `WHERE LOWER(model) = ? OR LOWER(model) LIKE ?` with params `(model.lower(), model.lower() + '::%')` to match exact model name and its `::` profile-suffixed variants only

#### Scenario: No false positives on prefix-similar model names
- **GIVEN** cache contains entries for "qwen3:1b" and "qwen3.5:9b::semiconductor"
- **WHEN** `clear(model="qwen3")` is called
- **THEN** only entries with model key exactly "qwen3" or starting with "qwen3::" SHALL be deleted
- **AND** entries for "qwen3:1b" and "qwen3.5:9b::semiconductor" SHALL NOT be deleted

#### Scenario: Clear all entries (no model filter)
- **GIVEN** cache contains entries for multiple models and profiles
- **WHEN** `clear()` is called without a model argument
- **THEN** all entries SHALL be deleted (unchanged behavior)

#### Scenario: API cache clear by model
- **GIVEN** a `DELETE /api/cache?model=qwen3.5:9b` request
- **WHEN** the cache clear is executed
- **THEN** all entries for "qwen3.5:9b" and all its `::` profile variants SHALL be cleared

### Requirement: Job Progress Logging with Profile Context
The job `[CONFIG]` log line SHALL include the active profile name so operators can identify which profile was used.

#### Scenario: Config log includes profile
- **GIVEN** a job created with profile "semiconductor"
- **WHEN** the job starts and emits the `[CONFIG]` log
- **THEN** the log SHALL include `profile=semiconductor` (e.g., `[CONFIG] model=qwen3.5:9b, profile=semiconductor, PDF output_format=docx, layout_mode=overlay`)

#### Scenario: Config log without profile
- **GIVEN** a job created without a profile (fallback to general)
- **WHEN** the job starts and emits the `[CONFIG]` log
- **THEN** the log SHALL include `profile=general`

### Requirement: Translation-Dedicated Model Backend Support
The system SHALL support translation-dedicated models (e.g., HY-MT1.5-7B) as an alternative to general-purpose models via the Ollama service.

#### Scenario: HY-MT1.5 translation via Ollama
- **GIVEN** Ollama service is running with HY-MT1.5-7B model loaded
- **WHEN** user selects the HY-MT translation profile and submits text for translation
- **THEN** the system SHALL send a fixed-template prompt without system prompt
- **AND** use translation-dedicated inference parameters
- **AND** return the translated text without additional commentary

#### Scenario: Model type passed through pipeline
- **GIVEN** a profile with model_type="translation" is selected
- **WHEN** a translation job is created
- **THEN** the model_type SHALL be passed from API route through job_manager, orchestrator, to OllamaClient
- **AND** the OllamaClient SHALL use the model_type to determine prompt and parameter strategy

#### Scenario: Cache isolation between model types
- **GIVEN** the same source text is translated by both a general and a translation-dedicated model
- **WHEN** cache keys are computed
- **THEN** the cache keys SHALL differ between model types
- **AND** cached translations from one model type SHALL NOT be returned for queries using a different model type

### Requirement: HY-MT Translation Profile
The system SHALL provide a predefined profile for the HY-MT1.5 translation-dedicated model.

#### Scenario: HY-MT profile available in profile list
- **WHEN** the client requests the profile list via GET /api/profiles
- **THEN** the response SHALL include an "hymt" profile
- **AND** the profile SHALL have model_type="translation"

#### Scenario: Profile list includes model_type field
- **WHEN** the client requests the profile list via GET /api/profiles
- **THEN** each profile in the response SHALL include a model_type field
- **AND** existing general profiles SHALL have model_type="general"

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

