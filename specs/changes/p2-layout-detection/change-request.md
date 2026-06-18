# Change Request

## Original Request

P2-1（改善計畫 §4.1.1）：在 `parsers/pdf_parser.py` 之後插入 `app/backend/parsers/layout_detector.py`，呼叫本地 **Docling heron-101（ONNX，`docling-project/docling-layout-heron-onnx`）** 把頁面切成 typed regions（text/title/table/figure/formula/header/footer/list），填入 `p2-ir-document-model` 定義的 `ElementType` 與 `reading_order`，取代 `round(y0,10pt)` 分桶啟發式（痛點 9）。模型權重以本地 HuggingFace / 離線權重載入，**不上傳頁面影像至外部服務**。

> **模型選型說明（2026/06 調查）**：原改善計畫指定 DocLayout-YOLO（0.91 mAP 係在自有 DocStructBench 上，DocLayNet benchmark 實為 79.7%）。調查後改採 Docling heron-101：在 DocLayNet 上 78.0% mAP（差距 1.7pp），但官方直接提供 ONNX 權重（`docling-project/docling-layout-heron-onnx`）、僅需 `onnxruntime`（無 ultralytics 依賴）、IBM Docling 持續維護、DocLayout-YOLO 自 2024Q4 後無主動演進。

## Business / User Goal

以版面感知偵測取代脆弱幾何啟發式，讓多欄 / 旋轉版面的閱讀順序正確、區域型別明確，為公式 pass-through、圖片排除翻譯、表格區處理鋪路。目標：多欄學術 PDF 閱讀順序正確率 > 95%。

## Non-goals

- 不做 OCR（掃描檔，P3-1）；本 change 僅針對有文字層的 native PDF 區域偵測。
- 不做公式 LaTeX 還原（P3-2）、不做表格 cell 拓樸辨識（P3-3）；僅標記 region 型別。
- 不改渲染器。

## Constraints

- **本地推論強制**：頁面影像不得送雲端；模型走本地 HuggingFace / ONNX runtime。
- 模型權重須可離線 bundle（Docker image 預載 + 離線權重路徑設定），緩解下載受網路限制風險（§5.1）。
- 授權：Apache-2.0 的 Docling heron-101（`docling-project/docling-layout-heron-onnx`），避免 GPL 靜態連結污染。
- 偵測結果寫入 `p2-ir-document-model` 的 IR，不得另立平行資料結構。
- 須以 `p2-ir-document-model` 黃金樣本做新舊閱讀順序雙跑比對。

## Known Context

- 前置：`p2-ir-document-model`（IR 須先具備 region 型別與 reading_order，已完成）
- PDF 解析：`app/backend/parsers/pdf_parser.py`、`app/backend/parsers/base.py`
- IR 模型：`app/backend/models/translatable_document.py`（已有 `ElementType`/`BoundingBox`/`TranslatableDocument`）
- 改善計畫 §2.3、§6.2、§6.3、§5.1 風險表（原文提及 DocLayout-YOLO；已換模型，見上方選型說明）
- 黃金樣本回歸測試集：`tests/fixtures/golden/`（由 `p2-ir-document-model` 建立）

## Open Questions

- ONNX runtime 與 GPU/CPU 推論的部署需求（是否需要 `onnxruntime-gpu`？預設 CPU-only）。
- 模型推論的失敗降級策略：heron 推論失敗時是否 fallback 回 `round(y0,10pt)` 啟發式，或直接錯誤？

## Requested Delivery Date / Priority

P2 軌道 A，Wave 2。前置 `p2-ir-document-model`（已完成）。
