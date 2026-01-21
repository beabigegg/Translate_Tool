# Change: 新增整合測試

## Why
目前僅有單元測試，缺少整合測試覆蓋關鍵功能。切換到地端模型後需要完整的測試驗證。

## What Changes
- 建立 `tests/` 目錄結構
- 新增文件處理器整合測試
- 新增快取持久化測試
- 新增測試用範例檔案

## Impact
- Affected specs: translator-core
- Affected code: 新增 `tests/` 目錄
