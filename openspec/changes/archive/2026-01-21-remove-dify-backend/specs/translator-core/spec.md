## MODIFIED Requirements

### Requirement: Type Annotations
The system SHALL use consistent type annotations throughout the codebase.

#### Scenario: Translation client type
- **WHEN** a function accepts a translation client parameter
- **THEN** the type annotation SHALL be `OllamaClient`
- **AND** no Union types with removed backends

#### Scenario: Type checking passes
- **WHEN** running mypy type checker
- **THEN** all type annotations SHALL be valid
- **AND** no errors related to removed DifyClient type

## ADDED Requirements

### Requirement: Local-Only Operation
The system SHALL operate entirely locally without requiring internet connectivity for translation.

#### Scenario: Offline translation
- **GIVEN** Ollama service is running locally
- **WHEN** user translates a document
- **THEN** translation completes without any network calls to external services
- **AND** no API keys or cloud credentials are required

#### Scenario: No cloud backend options
- **GIVEN** the application GUI is displayed
- **WHEN** user views translation settings
- **THEN** only local Ollama backend options are available
- **AND** no cloud service configuration fields are shown
