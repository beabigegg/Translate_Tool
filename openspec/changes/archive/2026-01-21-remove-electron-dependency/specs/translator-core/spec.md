## REMOVED Requirements

### Requirement: Electron Desktop Shell
**Reason**: Electron cannot operate in WSL2 environments; browser-based access provides equivalent functionality.
**Migration**: Users access the application via browser at http://localhost:5173

## MODIFIED Requirements

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

## ADDED Requirements

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
