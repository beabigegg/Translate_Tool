## ADDED Requirements

### Requirement: Translation Profile Definition
The system SHALL provide a set of predefined translation profiles, each consisting of an ID, display name, description, model name, and domain-specific system prompt.

#### Scenario: Available profiles
- **GIVEN** the system is initialized
- **WHEN** profiles are queried
- **THEN** the following profiles SHALL be available:
  - `general` — 通用翻譯 / General (default)
  - `government` — 正式公文 / Government Documents
  - `semiconductor` — 半導體產業 / Semiconductor
  - `fab` — 晶圓廠 / FAB
  - `manufacturing` — 傳統製造業 / Manufacturing
  - `financial` — 金融行業 / Financial
  - `legal` — 法律文件 / Legal

#### Scenario: Profile structure
- **GIVEN** any translation profile
- **WHEN** the profile is retrieved
- **THEN** it SHALL contain fields: `id` (str), `name` (str), `description` (str), `model` (str), `system_prompt` (str)

#### Scenario: Default profile fallback
- **GIVEN** a request with no profile specified or an invalid profile ID
- **WHEN** the profile is resolved
- **THEN** the system SHALL fall back to the `general` profile

### Requirement: Profile API Endpoint
The system SHALL expose a REST endpoint to list available translation profiles.

#### Scenario: List profiles
- **GIVEN** the backend is running
- **WHEN** a GET request is made to `/api/profiles`
- **THEN** the response SHALL be a bare JSON array (not wrapped in an object) of profile objects, each with `id`, `name`, and `description` fields
- **AND** the response content type SHALL be `application/json`

#### Scenario: Profile in job creation
- **GIVEN** a job creation request with `profile=semiconductor`
- **WHEN** the POST request is made to `/api/jobs`
- **THEN** the system SHALL resolve the profile and use its model and system prompt for translation
- **AND** the profile_id SHALL be threaded through job_manager → orchestrator → OllamaClient

### Requirement: Domain-Specific System Prompts
Each translation profile SHALL include a system prompt tailored to the domain's terminology, register, and formatting conventions. System prompts SHALL follow a consistent structure: role declaration, terminology guidance, register/tone, output rules, and numerical/code preservation.

> **Reference**: See `system-prompts.md` in this directory for the complete system prompt text for each profile.

#### Scenario: General profile system prompt
- **GIVEN** the `general` profile is selected
- **WHEN** the system prompt is applied
- **THEN** it SHALL instruct the model to translate accurately, preserving meaning and tone
- **AND** it SHALL specify output rules: only translated text, no explanations, no markdown wrapping, no commentary
- **AND** it SHALL instruct to preserve line breaks, numbers, and formatting

#### Scenario: Semiconductor profile system prompt
- **GIVEN** the `semiconductor` profile is selected
- **WHEN** the system prompt is applied
- **THEN** it SHALL instruct the model to use standard semiconductor terminology correctly and consistently
- **AND** it SHALL include guidance on terms such as: IC design, packaging, testing, MOSFET, FinFET, SOI, TSV, BGA, wafer, die, photomask, EDA
- **AND** it SHALL instruct to preserve technical abbreviations untranslated when they are industry standard

#### Scenario: FAB profile system prompt
- **GIVEN** the `fab` profile is selected
- **WHEN** the system prompt is applied
- **THEN** it SHALL instruct the model to use wafer fabrication terminology correctly
- **AND** it SHALL include guidance on terms such as: lithography, etching, deposition, CMP, yield, defect density, clean room, diffusion, implantation, metrology
- **AND** it SHALL instruct to preserve equipment vendor names (ASML, TEL, LAM, KLA, Applied Materials) as-is

#### Scenario: Manufacturing profile system prompt
- **GIVEN** the `manufacturing` profile is selected
- **WHEN** the system prompt is applied
- **THEN** it SHALL instruct the model to use general manufacturing terminology correctly
- **AND** it SHALL include guidance on terms such as: QC, SOP, FMEA, Lean, Six Sigma, Kaizen, ISO standards, production line, BOM, MRP, ERP
- **AND** it SHALL use a professional but accessible register appropriate for factory floor documentation

#### Scenario: Government profile system prompt
- **GIVEN** the `government` profile is selected
- **WHEN** the system prompt is applied
- **THEN** it SHALL instruct the model to use formal register and precise administrative terminology
- **AND** it SHALL instruct to preserve legal citation formats, regulatory references, and official document numbering
- **AND** it SHALL use the most formal grammatical constructions appropriate for the target language

#### Scenario: Financial profile system prompt
- **GIVEN** the `financial` profile is selected
- **WHEN** the system prompt is applied
- **THEN** it SHALL instruct the model to use standard financial terminology correctly
- **AND** it SHALL include guidance on terms such as: P&L, ROI, EBITDA, Basel, IFRS, GAAP, derivatives, hedging, margin, portfolio
- **AND** it SHALL instruct to preserve all numerical data, currency symbols, and financial figures exactly as-is

#### Scenario: Legal profile system prompt
- **GIVEN** the `legal` profile is selected
- **WHEN** the system prompt is applied
- **THEN** it SHALL instruct the model to use precise legal terminology and preserve clause structure without paraphrasing
- **AND** it SHALL include guidance on terms such as: indemnification, force majeure, jurisdiction, liability, arbitration, intellectual property, confidentiality, breach, remedy
- **AND** it SHALL instruct to preserve article/section numbering and cross-references exactly

### Requirement: System Prompt Output Rules
All profile system prompts SHALL include a common set of output rules to prevent verbosity and ensure clean translation output.

#### Scenario: Common output rules in all profiles
- **GIVEN** any profile's system prompt
- **WHEN** the system prompt is constructed
- **THEN** it SHALL include rules to: (1) output only the translated text, (2) never add explanations or commentary, (3) never wrap output in markdown code blocks or quotes, (4) preserve all `<<<SEG_N>>>` formatting markers if present, (5) preserve numbers, units, formulas, and model numbers exactly as-is, (6) if the input text is already entirely in the target language, return it unchanged without modification, (7) for short labels or column headers that already contain the target language translation alongside other languages (bilingual fields), return the original text unchanged

### Requirement: Profile Extensibility
Adding a new translation profile SHALL require only adding an entry to the profiles dictionary in `translation_profiles.py`, with no changes to other backend or frontend files.

#### Scenario: Adding a new profile
- **GIVEN** a developer adds a new profile entry to the `PROFILES` dict
- **WHEN** the backend restarts
- **THEN** the new profile SHALL appear in `GET /api/profiles` response
- **AND** be selectable from the frontend UI without frontend code changes
