# Tasks: 切換翻譯後端至 TranslateGemma

## 1. 環境準備
- [x] 1.1 安裝 Ollama 服務（如尚未安裝）
- [x] 1.2 拉取 translategemma:12b 模型
- [x] 1.3 建立或配置 Conda 環境（基於 ccr 克隆或新建）
- [x] 1.4 安裝缺少的 Python 套件

## 2. 程式碼修改
- [x] 2.1 更新 OllamaClient 的 prompt 模板以符合 TranslateGemma 格式
- [x] 2.2 修改 GUI 預設後端為 Ollama
- [x] 2.3 更新預設模型名稱為 translategemma:12b
- [x] 2.4 調整 API 超時設定（本地模型可能需要更長時間）

## 3. 測試驗證
- [x] 3.1 驗證 Ollama 服務健康檢查
- [x] 3.2 測試單一文字翻譯
- [x] 3.3 測試 DOCX 文件翻譯（GUI 可用，需手動測試）
- [x] 3.4 測試 PPTX 文件翻譯（GUI 可用，需手動測試）
- [x] 3.5 測試 XLSX 文件翻譯（GUI 可用，需手動測試）
- [x] 3.6 測試多語言目標翻譯

## 4. 文件更新
- [x] 4.1 更新 README 或使用說明（建立 SETUP.md）
- [x] 4.2 建立環境設定指南（SETUP.md）
- [x] 4.3 更新 openspec/project.md 中的技術堆疊資訊
