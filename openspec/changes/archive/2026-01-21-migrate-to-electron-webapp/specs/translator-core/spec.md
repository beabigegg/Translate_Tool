## ADDED Requirements
### Requirement: Web API Service
The system SHALL provide a local HTTP API for translation jobs and artifacts.

#### Scenario: Upload creates a job
- **GIVEN** a user uploads one or more supported files with target settings
- **WHEN** the API receives the multipart upload
- **THEN** the system stores files in a job workspace
- **AND** returns a job identifier

#### Scenario: Job status query
- **WHEN** the client requests job status
- **THEN** the system returns state and progress counts
- **AND** includes error details when a job fails

#### Scenario: Log stream
- **WHEN** the client opens the log stream endpoint
- **THEN** the system streams log lines as they are produced
- **AND** streaming does not block translation work

#### Scenario: Download results
- **WHEN** a job completes successfully
- **THEN** the system provides a downloadable archive of outputs
- **AND** results remain available until cleaned

#### Scenario: Cancel job
- **WHEN** the client requests job cancellation
- **THEN** the system signals stop and completes the current file
- **AND** the job status reports "stopped"

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

### Requirement: Electron Desktop Shell
The system SHALL package the web app into a desktop application using Electron.

#### Scenario: Launch desktop app
- **WHEN** the user launches the desktop app
- **THEN** the Electron main process starts the local backend
- **AND** opens the web UI in a desktop window

#### Scenario: Offline operation
- **GIVEN** no external network is available
- **WHEN** the user runs the desktop app
- **THEN** all translation features remain available locally

#### Scenario: App shutdown
- **WHEN** the user closes the desktop app
- **THEN** the backend process is stopped
- **AND** temporary job files are cleaned according to policy

## MODIFIED Requirements
### Requirement: Standard Logging Framework
The system SHALL use Python's standard logging module for all log output.

#### Scenario: Logging configuration
- **WHEN** the application starts
- **THEN** logging is configured with appropriate format
- **AND** format includes timestamp, level, module name, and message
- **AND** default level is INFO

#### Scenario: Log level control
- **WHEN** user wants to change log verbosity
- **THEN** log level can be configured (DEBUG, INFO, WARNING, ERROR)
- **AND** changes affect all log output

#### Scenario: File logging
- **WHEN** application runs
- **THEN** logs are written to a log file
- **AND** log file is rotated to prevent excessive size
- **AND** log file location is configurable

#### Scenario: Web UI log integration
- **WHEN** log messages are generated
- **THEN** they appear in the web UI log panel via the log stream endpoint
- **AND** they are also written to the log file
- **AND** UI display is not blocked by logging operations

### Requirement: Modular Architecture
The system SHALL be organized into separate modules for maintainability and testability.

#### Scenario: Module separation
- **WHEN** the application is structured
- **THEN** backend modules live under app/backend/ with clients/, processors/, cache/, services/, api/
- **AND** frontend UI lives under app/frontend/
- **AND** Electron shell lives under app/electron/
- **AND** utility functions are scoped to their respective modules

#### Scenario: Clean imports
- **WHEN** a module needs functionality from another module
- **THEN** it imports via the package's public interface
- **AND** circular imports are avoided

#### Scenario: Entry points
- **WHEN** the user starts the desktop application
- **THEN** the Electron main process serves as the primary entry point
- **AND** the backend provides a single server entry point for development
- **AND** CLI mode is not required

### Requirement: GUI Status Display During Resource Release
The GUI SHALL display resource release progress to the user.

#### Scenario: Status during release
- **GIVEN** a translation task has just completed
- **WHEN** resource release is in progress
- **THEN** the web UI status panel displays "Releasing resources..."

#### Scenario: Status after release
- **GIVEN** resource release has completed
- **WHEN** the UI updates
- **THEN** the status panel displays the final task result
- **AND** the Start action is re-enabled
