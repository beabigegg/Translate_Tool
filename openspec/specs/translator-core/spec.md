# translator-core Specification

## Purpose
TBD - created by archiving change fix-stop-button. Update Purpose after archive.
## Requirements
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

### Requirement: Document Size Limits
The system SHALL enforce document size limits to prevent memory exhaustion.

#### Scenario: Segment count limit exceeded
- **WHEN** a document contains more than MAX_SEGMENTS segments (default: 10,000)
- **THEN** the system raises an error before processing
- **AND** displays a user-friendly message indicating the limit and actual count

#### Scenario: Character count limit exceeded
- **WHEN** a document's total text exceeds MAX_TEXT_LENGTH characters (default: 100,000)
- **THEN** the system raises an error before processing
- **AND** displays a user-friendly message indicating the limit and actual count

#### Scenario: Document within limits
- **WHEN** a document is within both segment and character limits
- **THEN** processing proceeds normally
- **AND** no additional overhead is introduced

#### Scenario: Configurable limits
- **WHEN** user has configured custom limit values
- **THEN** the system uses the configured values instead of defaults

### Requirement: Configurable Timeout Settings
The system SHALL allow users to configure timeout values for API calls.

#### Scenario: Default timeout values
- **WHEN** no timeout configuration is provided
- **THEN** the system uses sensible default values
- **AND** connect timeout defaults to 10 seconds
- **AND** read timeout defaults to 180 seconds for local models

#### Scenario: Configuration file timeout
- **WHEN** timeout values are specified in configuration file
- **THEN** the system uses the configured values
- **AND** invalid values are rejected with clear error messages

#### Scenario: Environment variable timeout
- **WHEN** timeout values are specified via environment variables
- **THEN** environment variables take precedence over config file
- **AND** the system reads TRANSLATE_CONNECT_TIMEOUT and TRANSLATE_READ_TIMEOUT

#### Scenario: Runtime timeout adjustment
- **WHEN** user needs longer timeouts for slow models
- **THEN** the timeout can be adjusted without code changes
- **AND** changes take effect on next API call

### Requirement: Translation Cache Thread Safety
The translation cache SHALL be thread-safe and prevent deadlocks in multi-threaded environments.

#### Scenario: Concurrent cache reads
- **WHEN** multiple threads read from the cache simultaneously
- **THEN** each thread gets its own database connection
- **AND** reads complete without blocking each other
- **AND** connections are properly closed after use

#### Scenario: Concurrent cache writes
- **WHEN** multiple threads write to the cache simultaneously
- **THEN** writes are serialized via locking
- **AND** no data corruption occurs
- **AND** WAL mode enables concurrent reads during writes

#### Scenario: Connection cleanup
- **WHEN** a cache operation completes (success or failure)
- **THEN** the database connection is always closed
- **AND** no connection leaks occur over time

### Requirement: Batch Translation Support
The system SHALL support batch translation to improve performance when processing multiple text segments.

#### Scenario: Batch multiple segments
- **WHEN** multiple unique text segments need translation
- **THEN** the system collects segments up to the configured batch size
- **AND** sends them as a single translation request
- **AND** distributes results back to the appropriate segments

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

### Requirement: Consistent Type Annotations
The system SHALL have consistent type annotations for all public functions and class attributes.

#### Scenario: Function type annotations
- **WHEN** a public function is defined
- **THEN** it has type annotations for all parameters
- **AND** it has a return type annotation
- **AND** complex types use appropriate typing constructs (List, Dict, Optional, etc.)

#### Scenario: Class attribute annotations
- **WHEN** a class defines attributes
- **THEN** instance attributes have type annotations
- **AND** class variables have type annotations where applicable

#### Scenario: Type checking validation
- **WHEN** mypy is run on the codebase
- **THEN** no type errors are reported
- **AND** all public APIs are fully annotated

### Requirement: Modular Architecture
The system SHALL be organized into separate modules for maintainability and testability.

#### Scenario: Module separation
- **WHEN** the application is structured
- **THEN** backend modules live under app/backend/ with clients/, processors/, cache/, services/, api/
- **AND** frontend UI lives under app/frontend/
- **AND** utility functions are scoped to their respective modules

#### Scenario: Clean imports
- **WHEN** a module needs functionality from another module
- **THEN** it imports via the package's public interface
- **AND** circular imports are avoided

#### Scenario: Entry points
- **WHEN** the user starts the application
- **THEN** the startup script launches the backend server and frontend dev server
- **AND** displays the service URLs for browser access
- **AND** CLI mode is not required

### Requirement: Exception Handling
The system SHALL use specific exception types and log errors appropriately for debugging.

#### Scenario: Import error handling
- **WHEN** an optional library import fails
- **THEN** the system catches `ImportError` specifically
- **AND** logs the failure at debug level
- **AND** gracefully degrades functionality

#### Scenario: File operation error handling
- **WHEN** a file operation fails
- **THEN** the system catches `IOError` or `OSError` specifically
- **AND** logs the error with file path information
- **AND** provides a user-friendly error message

#### Scenario: API error handling
- **WHEN** an API call fails
- **THEN** the system catches the specific exception type (e.g., `RequestException`)
- **AND** logs the error with request details
- **AND** triggers retry logic if appropriate

#### Scenario: Unknown errors
- **WHEN** an unexpected error occurs
- **THEN** the system logs the full exception with traceback
- **AND** provides a generic error message to the user
- **AND** does not silently swallow the error

### Requirement: Integration Test Coverage
The system SHALL have integration tests covering key functionality.

#### Scenario: Document processor tests
- **WHEN** integration tests are run
- **THEN** DOCX, PPTX, and XLSX processors are tested with real files
- **AND** document content extraction is verified
- **AND** translated content insertion is verified

#### Scenario: Cache persistence tests
- **WHEN** cache persistence is tested
- **THEN** cache entries survive application restart
- **AND** cache lookup returns correct results
- **AND** cache handles concurrent access

#### Scenario: API client tests
- **WHEN** API client is tested
- **THEN** network failures trigger retry logic
- **AND** timeout handling is verified
- **AND** response parsing is validated

#### Scenario: Test fixtures
- **WHEN** tests require sample files
- **THEN** fixtures are available in `tests/fixtures/`
- **AND** fixtures cover various document formats
- **AND** fixtures include edge cases (empty, large, special characters)

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
- **THEN** the web UI status panel displays "Releasing resources..."

#### Scenario: Status after release
- **GIVEN** resource release has completed
- **WHEN** the UI updates
- **THEN** the status panel displays the final task result
- **AND** the Start action is re-enabled

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

### Requirement: Startup Script Service Management
The startup script SHALL manage both backend and frontend services with clear status output.

#### Scenario: Start services
- **WHEN** user runs `./translate_tool.sh start`
- **THEN** the script activates the conda environment
- **AND** starts the backend server (FastAPI on port 8765)
- **AND** starts the frontend server (Vite on port 5173)
- **AND** waits for backend health check to pass
- **AND** displays service URLs to the user

#### Scenario: Service URL display
- **WHEN** services start successfully
- **THEN** the script displays:
  - Frontend URL: http://localhost:5173
  - Backend URL: http://127.0.0.1:8765
- **AND** indicates the application is ready for use

#### Scenario: Stop services
- **WHEN** user runs `./translate_tool.sh stop`
- **THEN** the script stops the backend process
- **AND** stops the frontend process
- **AND** confirms services are stopped

#### Scenario: Status check
- **WHEN** user runs `./translate_tool.sh status`
- **THEN** the script displays running status of backend
- **AND** displays running status of frontend

