## MODIFIED Requirements

### Requirement: Default Backend Selection
The system SHALL use Ollama backend with TranslateGemma:12b model as the only translation backend.

#### Scenario: Application startup with Ollama available
- **GIVEN** Ollama service is running
- **WHEN** the application starts
- **THEN** the system SHALL connect to Ollama automatically
- **AND** the model dropdown SHALL default to "translategemma:12b" if available

#### Scenario: Application startup without Ollama
- **GIVEN** Ollama service is not running
- **WHEN** the application starts
- **THEN** the system SHALL display a warning that Ollama is not available
- **AND** prompt user to start Ollama service before translation

## REMOVED Requirements

### Requirement: Dify Cloud Backend Support
**Reason**: Application is transitioning to fully local operation; cloud translation service is no longer needed.
**Migration**: Users should ensure Ollama service with TranslateGemma model is installed and running.
