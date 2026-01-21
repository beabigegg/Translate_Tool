# Change: 新增可配置的超時設定

## Why
超時值目前硬編碼在程式中。使用地端模型時可能需要更長的超時時間，應允許使用者根據需求調整。

## What Changes
- 將超時值從硬編碼改為可配置
- 支援透過設定檔或環境變數配置
- 提供合理的預設值

## Impact
- Affected specs: translator-core
- Affected code: `document_translator_gui_with_backend.py:93-100`
