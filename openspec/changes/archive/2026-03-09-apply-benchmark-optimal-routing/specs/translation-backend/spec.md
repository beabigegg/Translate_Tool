## MODIFIED Requirements

### Requirement: 8GB VRAM Runtime Tuning Defaults
The system SHALL provide per-model-type runtime defaults tuned for RTX 4060 8GB-class environments. Model-level parameters (`num_ctx`, `num_gpu`, `kv_cache_type`) SHALL be managed in backend `config.py` via `MODEL_TYPE_OPTIONS`, not in the shell startup script. Decode parameters SHALL use benchmark-optimal greedy values as defaults.

#### Scenario: Per-model-type num_ctx defaults
- **GIVEN** no overriding environment variables are set
- **WHEN** backend configuration is loaded
- **THEN** general-purpose model type SHALL use `num_ctx=4096`
- **AND** translation-dedicated model type SHALL use `num_ctx=3072`
- **AND** both values SHALL fit within 8GB VRAM budget with their respective model sizes

#### Scenario: Greedy decode defaults for general model type
- **GIVEN** no overriding environment variables are set
- **WHEN** backend configuration is loaded
- **THEN** general-purpose model type SHALL use `temperature=0.05`, `top_p=0.50`, `top_k=10`, `repeat_penalty=1.0`, `frequency_penalty=0.0`

#### Scenario: Greedy decode defaults for translation model type
- **GIVEN** no overriding environment variables are set
- **WHEN** backend configuration is loaded
- **THEN** translation-dedicated model type SHALL use `temperature=0.05`, `top_p=0.50`, `top_k=10`, `repeat_penalty=1.0`, `frequency_penalty=0.0`

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

### Requirement: Profile-Driven Translation Backend
The system SHALL select the translation model and prompt strategy based on the resolved profile or automatic routing. The default model SHALL be `qwen3.5:4b`. The frontend SHALL send a `profile` identifier (or omit it for auto-routing); the backend resolves the profile to obtain the model name, model type, and system prompt. The `POST /api/jobs` endpoint SHALL NOT accept a `model` parameter.

#### Scenario: Successful translation with auto-routing (single target)
- **GIVEN** Ollama service is running
- **WHEN** user submits a job with one target language and no profile specified
- **THEN** the system SHALL use the model routing table to select the optimal model for that target
- **AND** apply the routed profile's system prompt and greedy decode parameters

#### Scenario: Successful translation with auto-routing (multi-target)
- **GIVEN** Ollama service is running
- **WHEN** user submits a job with multiple target languages and no profile specified
- **THEN** the system SHALL group targets by their optimal (model, profile_id, model_type) tuple
- **AND** call `process_files()` sequentially for each group with the group's optimal model
- **AND** all groups SHALL share the same output directory so output files accumulate

#### Scenario: Successful translation with explicit profile
- **GIVEN** Ollama service is running with the requested model loaded
- **WHEN** user submits text for translation with a selected profile
- **THEN** the system SHALL send the profile's system prompt via the Ollama `system` field
- **AND** send the source text with language direction via the `prompt` field
- **AND** return the translated text without additional commentary

#### Scenario: System prompt separation
- **GIVEN** a translation profile with a non-empty system prompt is selected
- **WHEN** the translation request is processed
- **THEN** the system SHALL include `"system": "<profile_system_prompt>"` in the Ollama API payload
- **AND** the `prompt` field SHALL contain only the language direction and source text
