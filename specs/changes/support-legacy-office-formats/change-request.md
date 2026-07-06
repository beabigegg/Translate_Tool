# Change Request

## Original Request

目前針對 Office 文件僅支援新版格式(docx/pptx/xlsx)。使用者要求評估並實作對舊版格式(.doc/.xls/.ppt)的完整支援,目標是「完整支援且維持品質」——舊格式的使用者體驗與翻譯品質應儘量對齊新格式,而非僅止於「能跑」。

User's exact follow-up after reviewing the current-state assessment: "好. 目標是完整支援且維持品質" (OK. Goal is full support while maintaining quality).

Scope agreed with user before scaffolding:
1. 補齊 `.ppt` 的 LibreOffice 轉檔支援(仿照既有 `doc_to_docx`/`xls_to_xlsx`,在 `app/backend/processors/libreoffice_helpers.py` 建立 `ppt_to_pptx`),並在 orchestrator 中比照 `.doc`/`.xls` 的既有分支接上 `.ppt` 路徑。
2. 既有的 `.doc`/`.xls` LibreOffice 轉檔路徑目前存在於 `app/backend/processors/orchestrator.py` 與 `libreoffice_helpers.py`,已列入 `SUPPORTED_EXTENSIONS`,但**沒有測試覆蓋、也沒有寫進 `environment.yml` 或任何安裝文件** — 需要補測試與安裝文件,讓這條路徑從「埋線但未驗證」變成可信賴的功能。
3. 前端 `app/frontend/src/constants/fileTypes.js` 的 `ACCEPTED_EXTENSIONS` 目前只有 `['.pdf', '.docx', '.txt', '.pptx', '.xlsx']`,需要開放 `.doc`/`.xls`/`.ppt` 上傳(UI 白名單、drop-zone 顯示文字)。
4. 評估並記錄轉檔導致的版面保真度風險與品質把關策略:轉檔後的舊格式文件應仍走現有的 layout detection / QE(quality evaluator)流程,且在必要時應向使用者揭露「舊格式為有損轉換,版面保真度可能低於原生新格式」的風險提示。

## Business / User Goal

讓使用者能上傳並取得舊版 Office 格式(.doc/.xls/.ppt)的高保真翻譯輸出,體驗與品質儘量對齊現有 docx/pptx/xlsx 路徑,而不是單純「檔案格式轉換後能跑完流程」。

## Non-goals

- 不重寫舊格式的原生解析器(不做逐位元組的 .doc/.xls/.ppt 二進位格式解析)— 轉檔策略維持透過 LibreOffice headless 轉為新格式後複用現有 pipeline。
- 不承諾與原生新格式完全等同的版面保真度(LibreOffice 轉檔本質上有損);目標是把差距縮小並讓風險透明化,而非消除轉檔本身的限制。

## Constraints

- LibreOffice 是外部二進位依賴,並非所有部署環境都會安裝;現有程式碼已經有 `is_libreoffice_available()` 的優雅降級檢查,新增的 `.ppt` 路徑與文件必須維持同樣的可選依賴語意(未安裝時給出清楚的錯誤訊息,而非硬性要求)。
- 需維持既有 CDD 契約狀態:任何 `SUPPORTED_EXTENSIONS` / API 行為變更需同步更新 `contracts/api/api-contract.md`(依專案慣例,變更 contract 後需重新 export `openapi.yml`)。

## Known Context

- 現況調查(本次對話已完成,可作為既有事實依據,不需要重新調查):
  - Backend `SUPPORTED_EXTENSIONS = {".docx", ".doc", ".pptx", ".xlsx", ".xls", ".pdf"}`(`app/backend/config.py:245`)已含 `.doc`/`.xls`,但缺 `.ppt`。
  - `app/backend/processors/libreoffice_helpers.py` 已有 `doc_to_docx()`、`xls_to_xlsx()`,以及 `is_libreoffice_available()` 偵測邏輯,但沒有對應測試檔案(`tests/` 中找不到 libreoffice 相關測試)。
  - `app/backend/processors/orchestrator.py` 中多處已有 `.doc`/`.xls` 的轉檔分支(如 line 104, 135, 243-244, 271-272, 334-335, 693, 700, 727-740, 783),但 `.ppt` 完全沒有對應分支。
  - 前端 `app/frontend/src/constants/fileTypes.js` 的 `ACCEPTED_EXTENSIONS = ['.pdf', '.docx', '.txt', '.pptx', '.xlsx']` 不含任何舊格式,使用者在 UI 上看不到 `.doc`/`.xls`/`.ppt` 選項。
  - `environment.yml`、README 等文件都沒有提及 LibreOffice 是可選依賴,也沒有安裝指引。

## Open Questions

- LibreOffice 轉檔後的版面保真度是否需要獨立的 QE 門檻或警示 UI(例如「此文件經過格式轉換,品質評分僅供參考」)?留給 contract-reviewer / spec-architect 評估是否需要新的 contract 欄位或 UI 提示。

## Requested Delivery Date / Priority

未指定明確日期;使用者已同意啟動,依一般優先序處理。
