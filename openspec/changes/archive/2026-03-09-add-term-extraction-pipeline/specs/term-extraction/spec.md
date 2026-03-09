## ADDED Requirements

### Requirement: Term Database Storage
The system SHALL maintain a local SQLite term database that stores source-to-target term mappings with domain and contextual metadata. The database SHALL enforce uniqueness on `(source_text, target_lang, domain)` to allow the same term to have different translations across domains.

#### Scenario: Store new term
- **WHEN** a new term translation is produced by Qwen 9B during Phase 0
- **THEN** the system SHALL insert a record with `source_text`, `target_text`, `source_lang`, `target_lang`, `domain`, `context_snippet`, `confidence`, and `usage_count=0`
- **AND** the record SHALL be committed to the SQLite database at `translated_files/term_db.sqlite`

#### Scenario: Skip duplicate term with same domain
- **GIVEN** a term `("Pin", "vi", "mechanical")` already exists in the database
- **WHEN** the same `(source_text, target_lang, domain)` is received again
- **THEN** the system SHALL NOT overwrite the existing record (default `skip` strategy)

#### Scenario: Same term with different domain stored separately
- **GIVEN** `("Pin", "vi", "electrical")` exists in the database
- **WHEN** `("Pin", "vi", "mechanical")` is inserted
- **THEN** both records SHALL coexist as distinct entries

#### Scenario: Increment usage count on lookup hit
- **WHEN** a term is retrieved from the database during translation
- **THEN** its `usage_count` SHALL be incremented by 1

---

### Requirement: Phase 0 Term Extraction
The system SHALL execute a full-document term extraction and translation phase (Phase 0) using the local Qwen 9B model before any translation begins. Phase 0 SHALL complete fully before Qwen 9B is unloaded and Phase 1 begins.

#### Scenario: Full document extraction before translation
- **GIVEN** a document is uploaded for translation
- **WHEN** the pipeline starts
- **THEN** the system SHALL scan all segments of the document with Qwen 9B to extract term candidates
- **AND** Phase 1 translation SHALL NOT begin until Phase 0 is complete and Qwen 9B is unloaded

#### Scenario: Term candidates extracted with wide definition
- **WHEN** Qwen 9B processes a segment
- **THEN** the extraction prompt SHALL request brand names, model numbers, equipment names, acronyms, process terms, action terms, and quality terms
- **AND** the following SHALL be excluded: ordinary verbs, adjectives, prepositions, numeric values and units (e.g. `100mm`, `±0.5`), document/form numbers (e.g. `SOP-001`, `Form-A`), version numbers (e.g. `Rev.1`), part numbers (e.g. `P/N: xxxxx`), and standalone codes (e.g. `OK`, `N/A`, `TBD`)
- **AND** each extracted term SHALL include a `context` field of ≤10 characters showing surrounding text

#### Scenario: Deduplication before DB lookup
- **GIVEN** the same term appears in multiple segments
- **WHEN** Phase 0 collects all extracted candidates
- **THEN** the system SHALL deduplicate by `(term, target_lang, domain)` before querying the Term DB

#### Scenario: Phase 0 Qwen 9B unloaded after extraction
- **WHEN** Phase 0 extraction and term translation are complete
- **THEN** the system SHALL unload Qwen 9B via `keep_alive=0`
- **AND** Phase 1 model loading SHALL proceed after unload confirmation

#### Scenario: Phase 0 failure does not abort translation
- **GIVEN** Qwen 9B fails or produces unparseable output during Phase 0
- **WHEN** the error occurs
- **THEN** the system SHALL log a warning with the failure detail
- **AND** translation SHALL proceed using only the terms already present in the local Term DB
- **AND** the pipeline SHALL NOT abort

---

### Requirement: Local Qwen 9B Term Translation
The system SHALL use the local Qwen 9B model to translate unknown terms during Phase 0, using the same Ollama instance already loaded for extraction.

#### Scenario: Unknown terms translated by Qwen 9B
- **GIVEN** Phase 0 has identified terms not present in the Term DB
- **WHEN** the translation prompt is sent to Qwen 9B
- **THEN** the prompt SHALL include `source_lang`, `target_lang`, `domain`, `document_context`, and the list of unknown terms with their context snippets
- **AND** the response SHALL be parsed as `{"translations": [{"source", "target", "confidence"}]}`
- **AND** results SHALL be written to the Term DB

#### Scenario: Brand names and model numbers preserved
- **GIVEN** an unknown term is a brand name or model number (e.g. `SMD C MAX`)
- **WHEN** Qwen 9B translates the term batch
- **THEN** such terms SHALL be returned unchanged with `confidence=1.0`

---

### Requirement: Domain Mapping from Scenario
The system SHALL derive the term domain from the already-detected Scenario, without requiring a separate domain-detection step.

#### Scenario: Scenario mapped to domain
- **GIVEN** the Scenario is `TECHNICAL_PROCESS`
- **WHEN** Phase 0 resolves the domain for term storage and prompt construction
- **THEN** the `domain` field SHALL be `"technical"`

#### Scenario: Scenario-to-domain mapping table
- **WHEN** the domain is resolved from any Scenario
- **THEN** the mapping SHALL be:
  - `TECHNICAL_PROCESS` → `"technical"`
  - `BUSINESS_FINANCE` → `"finance"`
  - `LEGAL_CONTRACT` → `"legal"`
  - `MARKETING_PR` → `"marketing"`
  - `DAILY_COMMUNICATION` → `"general"`
  - `GENERAL` → `"general"`

---

### Requirement: Terminology Prompt Injection
The system SHALL inject matched terms from the Term DB into Phase 1 and Phase 2 system prompts as `Terminology constraints`, rather than performing post-translation regex substitution. Injection SHALL be limited to the TOP_N most-used terms for the current document's domain.

#### Scenario: Terms injected into Phase 1 system prompt (Qwen single-phase)
- **GIVEN** matched terms exist in the Term DB for the current `(target_lang, domain)`
- **WHEN** a Qwen single-phase job builds its system prompt
- **THEN** a `Terminology constraints` block SHALL be appended listing source → target pairs

#### Scenario: Terms injected into HY-MT Phase 1 system prompt
- **GIVEN** HY-MT is the Phase 1 model and matched terms exist
- **WHEN** Phase 1 system prompt is assembled
- **THEN** the `Terminology constraints` block SHALL be appended to the HY-MT system prompt

#### Scenario: Terms injected into Phase 2 Refiner system prompt
- **GIVEN** Phase 2 Refiner is active and matched terms exist
- **WHEN** the Refiner system prompt is assembled
- **THEN** the `Terminology constraints` block SHALL be appended
- **AND** for Korean, this SHALL be the ONLY injection point (TranslateGemma has no system prompt)

#### Scenario: Injection capped at TOP_N terms
- **GIVEN** the Term DB has 200 entries for the current domain
- **WHEN** terms are injected into the system prompt
- **THEN** only the top 30 terms by `usage_count` SHALL be included (default TOP_N=30)

#### Scenario: No injection when no terms match
- **GIVEN** the Term DB has no entries for the current `(target_lang, domain)`
- **WHEN** system prompts are assembled
- **THEN** no `Terminology constraints` block SHALL be appended
- **AND** existing prompt content SHALL be unchanged

---

### Requirement: Term Database Export
The system SHALL support exporting the full term database to JSON, CSV, and XLSX formats.

#### Scenario: Export to JSON
- **WHEN** export is triggered with format `json`
- **THEN** the system SHALL write a JSON file with a `version`, `exported_at` timestamp, and `terms` array containing all fields per entry

#### Scenario: Export to CSV
- **WHEN** export is triggered with format `csv`
- **THEN** the system SHALL write a flat CSV with columns: `source_text`, `target_text`, `source_lang`, `target_lang`, `domain`, `context_snippet`, `confidence`, `usage_count`

#### Scenario: Export to XLSX
- **WHEN** export is triggered with format `xlsx`
- **THEN** the system SHALL write an XLSX file where each sheet corresponds to a unique `target_lang`

---

### Requirement: Term Database Import
The system SHALL support importing terms from JSON or CSV files with configurable conflict resolution.

#### Scenario: Import with skip strategy (default)
- **GIVEN** an import file contains a term whose `(source_text, target_lang, domain)` already exists in the DB
- **WHEN** import is run with strategy `skip`
- **THEN** the existing record SHALL be retained unchanged
- **AND** the new record SHALL be silently skipped

#### Scenario: Import with overwrite strategy
- **GIVEN** an import file contains a term that already exists in the DB
- **WHEN** import is run with strategy `overwrite`
- **THEN** the existing record SHALL be replaced with the imported values

#### Scenario: Import with merge strategy
- **GIVEN** an import file contains a term that already exists in the DB
- **WHEN** import is run with strategy `merge`
- **THEN** the record with the higher `confidence` value SHALL be kept
- **AND** if confidence values are equal, the existing record SHALL be retained

#### Scenario: Import summary reported
- **WHEN** an import completes
- **THEN** the system SHALL log counts of: terms inserted, terms skipped, terms overwritten
