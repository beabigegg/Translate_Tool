## Context
The application currently uses a Tkinter GUI and a monolithic Python script. The new goal is a local-only desktop web app with a modern UI, delivered via Electron and backed by a local Python API.

## Goals / Non-Goals
- Goals:
  - Provide a React + Vite UI for local translation workflows.
  - Expose translation functionality through a local HTTP API.
  - Package the app as a desktop application using Electron.
  - Keep all processing local (no cloud dependency).
- Non-Goals:
  - Cloud hosting or multi-user deployment.
  - Cross-device synchronization.

## Decisions
- Decision: Use FastAPI for the backend API and job management.
  - Rationale: Simple, async-friendly, works well with file uploads and streaming.
- Decision: Use React + Vite for the frontend.
  - Rationale: Fast dev workflow and modern UI stack.
- Decision: Use Electron for the desktop shell.
  - Rationale: Provides a local desktop wrapper with predictable packaging.
- Decision: Use SSE for log streaming.
  - Rationale: Simple to implement and sufficient for append-only logs.

## Risks / Trade-offs
- Electron packaging from WSL may not produce native Windows builds.
  - Mitigation: Target Windows + Linux builds; run Windows packaging on Windows host if needed.
- File uploads may be large and memory-intensive.
  - Mitigation: Stream uploads to disk and process from job workspace paths.

## Migration Plan
1. Extract backend modules from legacy script into app/backend/.
2. Add FastAPI API layer and job manager.
3. Build React + Vite frontend and integrate with API.
4. Add Electron shell to launch backend and serve UI.
5. Remove legacy Tkinter and CLI paths.

## Open Questions
- None (platform target assumed: Windows primary, Linux secondary).
