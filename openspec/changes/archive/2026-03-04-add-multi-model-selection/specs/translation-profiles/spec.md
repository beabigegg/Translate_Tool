## MODIFIED Requirements

### Requirement: Translation Profile Definition
The system SHALL provide a set of predefined translation profiles, each consisting of an ID, display name, description, model name, model type, and domain-specific system prompt.

#### Scenario: Available profiles
- **GIVEN** the system is initialized
- **WHEN** profiles are queried
- **THEN** the following profiles SHALL be available:
  - `general` — 通用翻譯 / General (default, model_type="general")
  - `government` — 正式公文 / Government Documents (model_type="general")
  - `semiconductor` — 半導體產業 / Semiconductor (model_type="general")
  - `fab` — 晶圓廠 / FAB (model_type="general")
  - `manufacturing` — 傳統製造業 / Manufacturing (model_type="general")
  - `financial` — 金融行業 / Financial (model_type="general")
  - `legal` — 法律文件 / Legal (model_type="general")
  - `hymt` — HY-MT 翻譯引擎 / HY-MT Translation Engine (model_type="translation")

#### Scenario: Profile structure
- **GIVEN** any translation profile
- **WHEN** the profile is retrieved
- **THEN** it SHALL contain fields: `id` (str), `name` (str), `description` (str), `model` (str), `system_prompt` (str), `model_type` (str, default "general")

#### Scenario: Default profile fallback
- **GIVEN** a request with no profile specified or an invalid profile ID
- **WHEN** the profile is resolved
- **THEN** the system SHALL fall back to the `general` profile

### Requirement: Profile API Endpoint
The system SHALL expose a REST endpoint to list available translation profiles and resolve profiles for job creation with model_type threading.

#### Scenario: Profile in job creation
- **GIVEN** a job creation request with `profile=semiconductor`
- **WHEN** the POST request is made to `/api/jobs`
- **THEN** the system SHALL resolve the profile and use its model, model_type, and system prompt for translation
- **AND** the profile_id SHALL be threaded through job_manager → orchestrator → OllamaClient
