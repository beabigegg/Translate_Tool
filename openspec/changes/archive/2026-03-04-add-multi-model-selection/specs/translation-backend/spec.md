## ADDED Requirements

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

## MODIFIED Requirements

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
