## ADDED Requirements

### Requirement: Resource Release After Task Completion
The system SHALL automatically release GPU VRAM and Python memory after translation tasks complete.

#### Scenario: Successful task completion triggers resource release
- **GIVEN** a translation task has completed successfully
- **WHEN** all files have been processed
- **THEN** the system SHALL call the Ollama API to unload the model
- **AND** the system SHALL call gc.collect() to release Python memory
- **AND** the system SHALL log resource release progress

#### Scenario: User interruption triggers resource release
- **GIVEN** a translation task is in progress
- **WHEN** the user clicks the Stop button and the task is interrupted
- **THEN** the system SHALL call resource release after stopping
- **AND** the system SHALL log that resources were released after interruption

#### Scenario: Error condition triggers resource release
- **GIVEN** a translation task encounters an unrecoverable error
- **WHEN** the task terminates due to the error
- **THEN** the system SHALL still attempt resource release
- **AND** the system SHALL not let release errors mask the original error

#### Scenario: Ollama service unavailable during release
- **GIVEN** a translation task has completed
- **WHEN** the Ollama service is not reachable during resource release
- **THEN** the system SHALL log a warning
- **AND** the system SHALL NOT raise an exception
- **AND** the system SHALL continue with Python gc.collect()

### Requirement: OllamaClient Model Unload Support
The OllamaClient SHALL provide a method to explicitly unload the model from VRAM.

#### Scenario: Unload model via API
- **GIVEN** an OllamaClient instance with a loaded model
- **WHEN** unload_model() is called
- **THEN** the system SHALL send a POST request to /api/generate
- **AND** the request SHALL include keep_alive: 0
- **AND** the request SHALL specify the current model name

#### Scenario: Unload returns success status
- **GIVEN** the Ollama service responds successfully to the unload request
- **WHEN** unload_model() completes
- **THEN** the method SHALL return (True, "Model unloaded successfully")

#### Scenario: Unload handles connection error
- **GIVEN** the Ollama service is not reachable
- **WHEN** unload_model() is called
- **THEN** the method SHALL return (False, error_message)
- **AND** the method SHALL NOT raise an exception

### Requirement: GUI Status Display During Resource Release
The GUI SHALL display resource release progress to the user.

#### Scenario: Status during release
- **GIVEN** a translation task has just completed
- **WHEN** resource release is in progress
- **THEN** the status label SHALL display "正在釋放資源..."

#### Scenario: Status after release
- **GIVEN** resource release has completed
- **WHEN** the GUI updates
- **THEN** the status label SHALL display the final task result
- **AND** the Start button SHALL be re-enabled
