## ADDED Requirements

### Requirement: Stop Button Functionality
The system SHALL allow users to stop ongoing translation work via the Stop button.

#### Scenario: User clicks Stop during translation
- **WHEN** user clicks the Stop button during file processing
- **THEN** the system sets the stop flag
- **AND** completes the current file being processed
- **AND** stops processing additional files
- **AND** displays a message indicating how many files were processed before stopping

#### Scenario: Stop flag checked at file level
- **WHEN** stop flag is set
- **THEN** the system checks the flag before starting each new file
- **AND** exits the processing loop if flag is set

#### Scenario: Stop flag checked at segment level
- **WHEN** stop flag is set during segment translation
- **THEN** the system checks the flag periodically during translation
- **AND** stops translation gracefully without corrupting the document
