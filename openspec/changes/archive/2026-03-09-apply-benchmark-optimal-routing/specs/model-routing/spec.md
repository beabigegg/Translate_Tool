## ADDED Requirements

### Requirement: Language-Based Model Routing
The system SHALL automatically select the optimal translation model, profile, and decode parameters based on the target language, using a benchmark-driven routing table.

#### Scenario: Routing for Vietnamese target
- **GIVEN** a translation job with target language "Vietnamese"
- **WHEN** the routing table is consulted
- **THEN** the system SHALL select HY-MT1.5-7B model with the `technical_process` profile
- **AND** apply greedy decode parameters (temperature=0.05, top_p=0.50, top_k=10)

#### Scenario: Routing for English target
- **GIVEN** a translation job with target language "English"
- **WHEN** the routing table is consulted
- **THEN** the system SHALL select Qwen3.5:4b model with the `general` profile
- **AND** apply greedy decode parameters

#### Scenario: Routing for Japanese target
- **GIVEN** a translation job with target language "Japanese"
- **WHEN** the routing table is consulted
- **THEN** the system SHALL select HY-MT1.5-7B model
- **AND** NOT use Qwen3.5:4b (benchmark showed catastrophic quality: Final=11.97)

#### Scenario: Routing for Korean target
- **GIVEN** a translation job with target language "Korean"
- **WHEN** the routing table is consulted
- **THEN** the system SHALL select TranslateGemma:4b model with the `general` profile

#### Scenario: Routing for unlisted target language
- **GIVEN** a translation job with a target language not in the routing table
- **WHEN** the routing table is consulted
- **THEN** the system SHALL default to Qwen3.5:4b with the `general` profile

#### Scenario: Multi-target routing groups by model
- **GIVEN** a translation job with multiple target languages ["English", "Vietnamese"]
- **WHEN** the routing table is consulted
- **THEN** the system SHALL group targets by their optimal (model, profile) pair
- **AND** "English" SHALL be routed to Qwen3.5:4b
- **AND** "Vietnamese" SHALL be routed to HY-MT1.5-7B
- **AND** each group SHALL be processed as a separate `process_files()` pass with its optimal model

#### Scenario: Multi-target same-model grouping
- **GIVEN** a translation job with target languages ["Vietnamese", "Japanese", "German"]
- **WHEN** the routing table is consulted
- **THEN** all three SHALL be grouped into a single HY-MT1.5-7B group
- **AND** processed in one `process_files()` pass

#### Scenario: Multi-group sequential execution
- **GIVEN** a job with targets grouped into multiple model groups
- **WHEN** the job executes
- **THEN** each group SHALL be processed sequentially (8GB VRAM constraint)
- **AND** all groups SHALL share the same output directory
- **AND** a stop request SHALL halt execution across all groups

### Requirement: Routing Table Structure
The routing module SHALL define a static mapping from target language to (model_key, profile_id) pairs, plus per-model greedy decode parameter presets.

#### Scenario: Routing table content
- **GIVEN** the routing module is loaded
- **WHEN** the routing table is inspected
- **THEN** it SHALL contain explicit entries for: Vietnamese, German, Japanese (→ HY-MT), Korean (→ TranslateGemma)
- **AND** all other languages SHALL fall back to Qwen3.5:4b

#### Scenario: Greedy decode presets
- **GIVEN** any model is selected by the router
- **WHEN** decode parameters are resolved
- **THEN** the greedy preset SHALL be: temperature=0.05, top_p=0.50, top_k=10, repeat_penalty=1.0, frequency_penalty=0.0

### Requirement: Manual Profile Override
The system SHALL allow users to override the automatic routing by explicitly specifying a profile.

#### Scenario: Explicit profile overrides routing
- **GIVEN** a translation job with target language "Vietnamese" and profile="general"
- **WHEN** the job is created
- **THEN** the system SHALL use the `general` profile (Qwen3.5:4b) instead of the routed HY-MT model
- **AND** the routing table SHALL be bypassed

#### Scenario: No profile specified uses auto-routing
- **GIVEN** a translation job with target language "Vietnamese" and no profile specified (or profile="auto")
- **WHEN** the job is created
- **THEN** the system SHALL use automatic routing to select the optimal model

### Requirement: Route Info API Endpoint
The system SHALL expose a REST endpoint that returns the recommended model for each target language, allowing the frontend to display routing information.

#### Scenario: Query route info for single target
- **GIVEN** a GET request to `/api/route-info?targets=Vietnamese`
- **WHEN** the endpoint responds
- **THEN** the response SHALL include the model name, profile ID, and model type for "Vietnamese"

#### Scenario: Query route info for multiple targets
- **GIVEN** a GET request to `/api/route-info?targets=English,Vietnamese,Japanese`
- **WHEN** the endpoint responds
- **THEN** the response SHALL include routing info for each target language
- **AND** indicate which target is the primary (first) one used for the job

#### Scenario: Route info response format
- **GIVEN** a route info query
- **WHEN** the response is returned
- **THEN** it SHALL be a JSON object with a `routes` array, each entry containing `target`, `model`, `profile_id`, and `model_type` fields
