# Design: TranslateGemma 整合設計

## Context
本專案需要將翻譯後端從雲端 Dify API 遷移至本地 Ollama + TranslateGemma:12b，以實現離線翻譯、降低成本並提升隱私保護。

### 利害關係人
- 終端使用者：需要穩定、快速的文件翻譯功能
- 開發者：需要維護簡單、易於測試的程式碼

### 限制條件
- GPU 記憶體：TranslateGemma:12b 約需 8-10GB VRAM（或可降級 CPU）
- 磁碟空間：模型約 8GB
- 現有程式碼：需保持向後相容，Dify 選項仍可用

## Goals / Non-Goals

### Goals
- 整合 TranslateGemma:12b 作為主要翻譯引擎
- 建立符合專案需求的 Conda 環境
- 保持現有功能完整性
- 優化本地翻譯效能

### Non-Goals
- 不移除 Dify 支援（保留作為備選）
- 不修改文件處理邏輯
- 不變更快取機制

## Decisions

### Decision 1: 使用 Ollama 作為模型服務層
**選擇**: Ollama REST API
**原因**:
- 程式碼已有 OllamaClient 實作
- 簡化模型管理（拉取、更新、版本控制）
- 提供標準化的 API 介面
- 支援 GPU/CPU 自動切換

**替代方案考量**:
- 直接使用 Hugging Face Transformers：需要更多程式碼修改，記憶體管理較複雜
- vLLM：效能更好但設定複雜，對此專案過度設計

### Decision 2: TranslateGemma Prompt 格式
**選擇**: 採用官方建議的 Prompt 模板
```
You are a professional {SOURCE_LANG} ({SOURCE_CODE}) to {TARGET_LANG} ({TARGET_CODE}) translator.
Your goal is to accurately convey the meaning and nuances of the original {SOURCE_LANG} text
while adhering to {TARGET_LANG} grammar, vocabulary, and cultural sensitivities.
Produce only the {TARGET_LANG} translation, without any additional explanations or commentary.
Please translate the following {SOURCE_LANG} text into {TARGET_LANG}: {TEXT}
```

**語言代碼對照**:
| 語言 | 代碼 |
|------|------|
| English | en |
| Vietnamese | vi |
| Traditional Chinese | zh-TW |
| Simplified Chinese | zh-CN |
| Japanese | ja |
| Korean | ko |

### Decision 3: Conda 環境策略
**選擇**: 克隆 ccr 環境並命名為 `translate-tool`
**原因**:
- ccr 環境已有 Python 3.11.14
- 已安裝 requests, openpyxl, python-docx
- 減少重複下載相同套件

**執行指令**:
```bash
# 方案 A: 克隆現有環境
conda create --name translate-tool --clone ccr
conda activate translate-tool
pip install python-pptx PyPDF2 blingfire pysbd

# 方案 B: 全新環境（如 ccr 有其他依賴衝突）
conda create -n translate-tool python=3.11.14
conda activate translate-tool
pip install requests python-docx python-pptx openpyxl PyPDF2 blingfire pysbd
```

### Decision 4: API 超時調整
**選擇**: 增加本地模型超時時間
- `API_CONNECT_TIMEOUT_S`: 10 → 10（不變）
- `API_READ_TIMEOUT_S`: 60 → 180（增加，本地推理較慢）

## Risks / Trade-offs

| 風險 | 機率 | 影響 | 緩解措施 |
|------|------|------|----------|
| GPU 記憶體不足 | 中 | 高 | 提供 CPU 降級指南 |
| 翻譯品質不一致 | 低 | 中 | 保留 Dify 備選 |
| Ollama 服務崩潰 | 低 | 中 | 健康檢查 + 重試 |
| 首次推理延遲高 | 高 | 低 | 預熱提示或載入指示 |

## Migration Plan

### 階段 1: 安裝準備（不影響現有功能）
1. 安裝 Ollama
2. 拉取 TranslateGemma:12b
3. 建立 Conda 環境

### 階段 2: 程式碼更新
1. 更新 OllamaClient prompt 模板
2. 調整預設設定
3. 增加語言代碼對照

### 階段 3: 測試驗證
1. 單元測試
2. 整合測試
3. 效能基準測試

### Rollback 計畫
如遇嚴重問題：
1. GUI 切換回 Dify 後端
2. 或在程式碼中將預設後端改回 Dify

## Open Questions
1. 是否需要支援 TranslateGemma 的多模態翻譯（圖片內文字）？
2. 是否需要在 GUI 中顯示模型載入狀態？
3. CPU-only 模式是否需要單獨的配置選項？
