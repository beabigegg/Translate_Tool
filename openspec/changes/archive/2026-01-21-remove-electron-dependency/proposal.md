# Change: Remove Electron Desktop Shell Dependency

## Why
Electron cannot run properly in WSL2 environments due to GUI limitations. The web-based interface provides full functionality through a browser, making the Electron wrapper unnecessary.

## What Changes
- **BREAKING**: Remove Electron desktop application support
- Modify startup script to directly manage backend and frontend services
- Add service URL display for user convenience
- Update modular architecture to reflect browser-only deployment

## Impact
- Affected specs: `translator-core`
- Affected code:
  - `app/electron/` (to be deleted)
  - `translate_tool.sh` (modify to start backend directly)
