## 1. Proposal
- [x] 1.1 Review and approve proposal

## 2. Backend (FastAPI)
- [x] 2.1 Create backend package structure under app/backend/
- [x] 2.2 Port translation logic into modules (config, clients, cache, processors, services)
- [x] 2.3 Implement job manager (create, progress, cancel, cleanup)
- [x] 2.4 Implement API endpoints (upload, status, logs, download, cancel)
- [x] 2.5 Preserve cache and resource release behavior

## 3. Frontend (React + Vite)
- [x] 3.1 Scaffold Vite + React frontend under app/frontend/
- [x] 3.2 Build upload + language ordering UI
- [x] 3.3 Add settings (timeouts, batch size)
- [x] 3.4 Add progress, logs, stop, download UI
- [x] 3.5 Wire API client and error handling

## 4. Electron Shell
- [x] 4.1 Scaffold Electron main process under app/electron/
- [x] 4.2 Start backend process and wait for health check
- [x] 4.3 Load frontend (dev server for dev, static build for prod)
- [x] 4.4 Configure packaging for Windows and Linux

## 5. Environment and Tooling
- [x] 5.1 Create minimal backend requirements/environment file
- [x] 5.2 Create frontend package.json with Electron tooling
- [x] 5.3 Add run scripts for dev and prod
- [x] 5.4 Add root start/stop script with conda checks
