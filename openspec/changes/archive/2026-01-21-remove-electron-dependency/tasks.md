## 1. Remove Electron

- [x] 1.1 Delete `app/electron/` directory

## 2. Update Startup Script

- [x] 2.1 Remove electron-related dependency checks from `translate_tool.sh`
- [x] 2.2 Add backend process management (start/stop/status)
- [x] 2.3 Add service URL display after successful startup
- [x] 2.4 Add backend health check before displaying URLs

## 3. Verification

- [x] 3.1 Test `./translate_tool.sh start` - verify backend and frontend start
- [x] 3.2 Test `./translate_tool.sh status` - verify status display
- [x] 3.3 Test `./translate_tool.sh stop` - verify clean shutdown
- [x] 3.4 Test browser access to frontend URL
