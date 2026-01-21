# Change: Migrate to Electron Web App

## Why
The current Tkinter GUI limits user experience and distribution options. A local web app with Electron provides a modern UI, offline operation, and consistent desktop packaging while keeping all processing on the local machine.

## What Changes
- **BREAKING** Replace the Tkinter GUI with a React + Vite frontend served by a local FastAPI backend.
- Add a job-based HTTP API for uploads, status, logs, cancellation, and downloads.
- Package the app with Electron, launching the local backend and loading the UI.
- Remove CLI mode and any DIFY-related remnants from the legacy code.
- Modularize backend code into clear packages and introduce a standard project layout.
- Update backend and frontend dependency manifests.

## Impact
- Affected specs: translator-core
- Affected code: app/document_translator_gui_with_backend.py (split), new app/backend/, app/frontend/, app/electron/
