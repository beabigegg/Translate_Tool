## Context
目前所有程式碼都在單一檔案中，隨著功能增加和修改，維護成本越來越高。需要重構為模組化架構以提升可維護性。

## Goals / Non-Goals
- Goals:
  - 將 1,540 行的單體檔案拆分為邏輯模組
  - 降低模組間的耦合度
  - 提升程式碼可測試性
- Non-Goals:
  - 不改變現有功能行為
  - 不引入新的外部依賴

## Decisions
- Decision: 採用扁平的套件結構
- Alternatives considered:
  - 深層巢狀結構 - 過度複雜，不適合此專案規模
  - 單一模組拆分 - 不夠清晰

## Target Structure
```
translate_tool/
├── __init__.py
├── main.py                    # 入口點
├── config.py                  # 設定管理
├── gui/
│   ├── __init__.py
│   └── translator_gui.py      # GUI 元件
├── clients/
│   ├── __init__.py
│   ├── base.py                # 抽象基底類別
│   └── ollama_client.py       # Ollama 客戶端
├── processors/
│   ├── __init__.py
│   ├── base.py                # 處理器介面
│   ├── docx_processor.py
│   ├── pptx_processor.py
│   ├── xlsx_processor.py
│   └── pdf_processor.py
├── cache/
│   ├── __init__.py
│   └── translation_cache.py
└── utils/
    ├── __init__.py
    └── text_utils.py
```

## Risks / Trade-offs
- 重構過程可能引入 bug → 透過完整測試覆蓋緩解
- Import 路徑變更 → 提供向後相容的入口點

## Migration Plan
1. 建立新的目錄結構
2. 逐一抽取模組
3. 更新 import 路徑
4. 執行測試確認功能正常
5. 移除舊的單體檔案

## Open Questions
- 無
