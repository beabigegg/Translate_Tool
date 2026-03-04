## RENAMED Requirements
- FROM: `### Requirement: TranslateGemma Local Translation Backend`
- TO: `### Requirement: Profile-Driven Translation Backend`

## MODIFIED Requirements

### Requirement: Profile-Driven Translation Backend
The system SHALL select the translation model and prompt strategy based on the resolved profile. The default model SHALL be `qwen3.5:9b`. The frontend SHALL only send a `profile` identifier; the backend resolves the profile to obtain the model name and system prompt. The `POST /api/jobs` endpoint SHALL NOT accept a `model` parameter.

#### Scenario: Successful translation with Qwen 3.5
- **GIVEN** Ollama service is running with `qwen3.5:9b` model loaded
- **WHEN** user submits text for translation with a selected profile
- **THEN** the system SHALL send the profile's system prompt via the Ollama `system` field
- **AND** send the source text with language direction via the `prompt` field
- **AND** return the translated text without additional commentary

#### Scenario: System prompt separation
- **GIVEN** a translation profile with a non-empty system prompt is selected
- **WHEN** the translation request is processed
- **THEN** the system SHALL include `"system": "<profile_system_prompt>"` in the Ollama API payload
- **AND** the `prompt` field SHALL contain only the language direction and source text

#### Scenario: Internal backward compatibility with TranslateGemma models
- **GIVEN** a profile whose `model` field contains "translategemma" in its name
- **WHEN** the translation request is processed
- **THEN** the system SHALL use the existing TranslateGemma prompt format (all instructions in `prompt`)
- **AND** SHALL NOT include a `system` field in the payload
- **AND** SHALL ignore the profile's `system_prompt` field

#### Scenario: TranslateGemma with auto-detect source language
- **GIVEN** a profile whose `model` field contains "translategemma" and `src_lang` is `"auto"` or empty/None
- **WHEN** the translation request is processed
- **THEN** the system SHALL treat `"auto"` the same as `None` and fall back to `"English"` as the source language in the TranslateGemma prompt
- **AND** the `_build_translategemma_prompt` method SHALL treat both `None`/empty and `"auto"` as missing, defaulting to `"English"`

#### Scenario: Auto-detect source language prompt
- **GIVEN** an OllamaClient with a system_prompt set and `src_lang` is `"auto"` or empty
- **WHEN** the user prompt is constructed
- **THEN** the language direction line SHALL be `"Translate to {tgt}:"` (omitting the source language)
- **AND** the model SHALL infer the source language from the input text

#### Scenario: Explicit source language prompt
- **GIVEN** an OllamaClient with a system_prompt set and `src_lang` is a specific language (e.g., `"English"`)
- **WHEN** the user prompt is constructed
- **THEN** the language direction line SHALL be `"Translate from {src} to {tgt}:"` (unchanged from current)

#### Scenario: Language code mapping
- **GIVEN** a target language name from the UI (e.g., "Traditional Chinese")
- **WHEN** constructing the translation prompt
- **THEN** the system SHALL map to the correct ISO language code (e.g., "zh-TW")

### Requirement: Default Model Selection
The system SHALL default to `qwen3.5:9b` model when available.

#### Scenario: Application startup with Ollama available
- **GIVEN** Ollama service is running
- **WHEN** the application starts
- **THEN** the system SHALL use `qwen3.5:9b` as the default model

#### Scenario: Application startup without Ollama
- **GIVEN** Ollama service is not running
- **WHEN** the application starts
- **THEN** the system SHALL display a warning that Ollama is not available

## ADDED Requirements

### Requirement: 8GB VRAM Runtime Tuning Defaults
The system SHALL provide runtime defaults tuned for RTX 4060 8GB-class environments to improve long-text coherence while minimizing VRAM↔RAM paging overhead.

#### Scenario: Backend config defaults for tuned context
- **GIVEN** no overriding environment variables are set
- **WHEN** backend configuration is loaded
- **THEN** `OLLAMA_NUM_CTX` default SHALL be `5120`
- **AND** `DEFAULT_READ_TIMEOUT_S` SHALL be `360`
- **AND** `MAX_PARAGRAPH_CHARS` SHALL be `2400`
- **AND** `MAX_MERGE_SEGMENTS` SHALL be `12`

#### Scenario: Startup script applies tuned defaults but preserves overrides
- **GIVEN** `translate_tool.sh start` is used
- **WHEN** runtime environment variables are unset
- **THEN** the script SHALL set defaults: `OLLAMA_NUM_CTX=5120`, `OLLAMA_NUM_GPU=99`, `TRANSLATE_CONNECT_TIMEOUT=15`, `TRANSLATE_READ_TIMEOUT=360`
- **AND** if any of these variables are pre-set by the user, the script SHALL keep the user-provided values unchanged

#### Scenario: Fallback when near-limit context is unstable
- **GIVEN** an 8GB GPU environment experiences instability or severe slowdown with `OLLAMA_NUM_CTX=5120`
- **WHEN** runtime tuning is adjusted
- **THEN** lowering `OLLAMA_NUM_CTX` to `4608` SHALL be the documented first-line fallback
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
