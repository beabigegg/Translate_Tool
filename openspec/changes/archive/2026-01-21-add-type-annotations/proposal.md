# Change: 完善型別註解

## Why
部分函式有型別提示，部分沒有，造成程式碼風格不一致且難以使用 IDE 的型別檢查功能。

## What Changes
- 為所有公開函式新增型別註解
- 為類別屬性新增型別註解
- 確保型別註解風格一致

## Impact
- Affected specs: translator-core
- Affected code: `document_translator_gui_with_backend.py` 全檔
