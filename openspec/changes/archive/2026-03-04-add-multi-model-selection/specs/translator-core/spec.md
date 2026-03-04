## ADDED Requirements

### Requirement: Model Type System
The system SHALL support multiple model types that determine prompt building strategy, inference parameters, and batch translation behavior.

#### Scenario: General-purpose model type
- **WHEN** a profile with `model_type="general"` is selected
- **THEN** the system SHALL use the profile's system prompt in the Ollama payload
- **AND** build user prompts with the existing "Translate from X to Y:" format
- **AND** use general inference parameters (frequency_penalty=0.5, think=False)

#### Scenario: Translation-dedicated model type
- **WHEN** a profile with `model_type="translation"` is selected
- **THEN** the system SHALL NOT send a system prompt to Ollama
- **AND** build prompts using a fixed English translation template
- **AND** use dedicated inference parameters (top_k=20, top_p=0.6, repeat_penalty=1.05, temperature=0.7)

#### Scenario: Model type defaults to general
- **WHEN** a profile does not specify a model_type
- **THEN** the system SHALL default to `model_type="general"`
- **AND** existing profiles continue to work without modification

### Requirement: Translation-Dedicated Prompt Template
The system SHALL use a single English fixed template for translation-dedicated models regardless of the language pair.

#### Scenario: Translation-dedicated prompt format
- **WHEN** text is submitted for translation
- **AND** the model type is translation-dedicated
- **THEN** the system SHALL use the English prompt template: "Translate the following segment into {target_language}, without additional explanation.\n\n{text}"
- **AND** the system SHALL NOT use a system prompt

## MODIFIED Requirements

### Requirement: Batch Translation Support
The system SHALL support batch translation to improve performance when processing multiple text segments.

#### Scenario: Batch multiple segments
- **WHEN** multiple unique text segments need translation
- **AND** the model type is general-purpose
- **THEN** the system collects segments up to the configured batch size
- **AND** sends them as a single translation request with <<<SEG_N>>> markers
- **AND** distributes results back to the appropriate segments

#### Scenario: Translation-dedicated model batch fallback
- **WHEN** multiple unique text segments need translation
- **AND** the model type is translation-dedicated
- **THEN** the system SHALL translate each segment individually
- **AND** NOT use <<<SEG_N>>> markers (unsupported by translation-dedicated models)

#### Scenario: Merged paragraph translation with translation-dedicated model
- **WHEN** merged context translation is enabled
- **AND** the model type is translation-dedicated
- **THEN** the system SHALL skip merging and translate each paragraph individually
- **AND** NOT inject marker preservation instructions

#### Scenario: Configurable batch size
- **WHEN** user configures batch size in settings
- **THEN** the system respects the configured batch size
- **AND** defaults to a sensible value (e.g., 10) if not configured

#### Scenario: Single segment fallback
- **WHEN** only one segment needs translation
- **THEN** the system handles it without batching overhead
- **AND** maintains backward compatibility with existing behavior

#### Scenario: Batch error handling
- **WHEN** a batch translation request fails
- **THEN** the system falls back to individual segment translation
- **AND** logs the batch failure for debugging

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
- **WHEN** the user changes batch size or timeout settings
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
