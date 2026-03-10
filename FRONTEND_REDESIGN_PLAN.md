# Translate Tool 前端重新設計計畫

## 目錄

1. [資訊架構 (Information Architecture)](#1-資訊架構)
2. [頁面設計 (Page Designs)](#2-頁面設計)
3. [元件庫規劃 (Component Library Plan)](#3-元件庫規劃)
4. [互動流程 (Interaction Flows)](#4-互動流程)
5. [視覺設計方向 (Visual Design Direction)](#5-視覺設計方向)
6. [響應式策略 (Responsive Strategy)](#6-響應式策略)
7. [技術架構建議 (Technical Architecture)](#7-技術架構建議)

---

## 1. 資訊架構

### 1.1 頁面結構與路由規劃

應用程式從單頁面拆分為五個主要路由頁面，搭配持久性的 Shell 佈局（側邊導覽 + 頂部列）：

```
/                        → 翻譯工作台（首頁、主要工作流程）
/terms                   → 術語庫管理（完整頁面）
/terms/review            → 術語審核子頁面
/settings                → 設定中心
/history                 → 翻譯歷史紀錄
```

### 1.2 導覽層級

```
┌──────────────────────────────────────────────────────┐
│  頂部列 (Top Bar)                                     │
│  [Logo] [頁面標題]              [健康指標] [暗色切換]  │
├────────┬─────────────────────────────────────────────┤
│ 側邊欄  │  主內容區                                    │
│        │                                              │
│ 翻譯   │                                              │
│ 術語庫  │                                              │
│ 歷史   │                                              │
│ 設定   │                                              │
│        │                                              │
│        │                                              │
│ ────── │                                              │
│ 系統   │                                              │
│ 狀態   │                                              │
└────────┴─────────────────────────────────────────────┘
```

**側邊欄底部固定區域**：顯示 Ollama 連線狀態指標（綠點/紅點）、GPU VRAM 使用率迷你進度條。這兩項資訊在所有頁面恆常可見，讓使用者隨時掌握系統狀態。

### 1.3 路由方案

| 路由 | 用途 | 對應的主要 API |
|------|------|----------------|
| `/` | 翻譯工作台：上傳、選語言、執行、監控 | `/api/jobs`, `/api/route-info` |
| `/terms` | 術語庫總覽：統計、匯出入 | `/api/terms/stats`, `/api/terms/export`, `/api/terms/import` |
| `/terms/review` | 待審核/已核准術語列表 | `/api/terms/unverified`, `/api/terms/approved`, `/api/terms/approve`, `/api/terms/edit` |
| `/settings` | 所有設定集中管理 | `/api/model-config`, `/api/profiles`, `/api/health` |
| `/history` | 翻譯工作紀錄 | `/api/stats`, `/api/cache/stats` |

---

## 2. 頁面設計

### 2.1 翻譯工作台 (`/`)

這是主要工作流程頁面，採用**精靈式（Wizard）三步驟**設計，步驟指示器可點擊切換（不再只是裝飾）。

#### 佈局結構

```
┌──────────────────────────────────────────────────┐
│  步驟指示器（可點擊）                               │
│  [1 上傳檔案] ──── [2 語言與設定] ──── [3 翻譯下載]  │
├──────────────────────────────────────────────────┤
│                                                    │
│  步驟內容區（根據目前步驟顯示不同內容）                 │
│                                                    │
└──────────────────────────────────────────────────┘
```

#### 步驟一：上傳檔案

```
┌──────────────────────────────────────────────────┐
│  拖放區域                                         │
│                                                   │
│     [雲朵圖示]                                     │
│     將檔案或資料夾拖放至此                           │
│     [選擇檔案] [選擇資料夾]                         │
│     支援格式：DOC, DOCX, PPTX, XLS, XLSX, PDF     │
│                                                   │
├──────────────────────────────────────────────────┤
│  已選檔案 (3 個)                      [全部清除]    │
│  ┌────────────────────────────────────────┐       │
│  │ [W] report.docx        2.3 MB    [x]  │       │
│  │ [X] data.xlsx           1.1 MB    [x]  │       │
│  │ [P] slides.pptx         5.7 MB    [x]  │       │
│  └────────────────────────────────────────┘       │
│                                                   │
│                     [下一步：選擇語言 →]             │
└──────────────────────────────────────────────────┘
```

- 拖放區域佔據主要視覺空間
- 檔案列表採卡片式，顯示檔案類型圖示、名稱、大小
- 「下一步」按鈕置於右下角，只有至少選取一個檔案後才啟用

#### 步驟二：語言與設定

採用**左右分欄佈局**，左側為必填項目（目標語言），右側為選填設定。

```
┌────────────────────────┬─────────────────────────┐
│  目標語言               │  翻譯設定                │
│                         │                         │
│  常用語言（核取方塊格）   │  模式切換                │
│  ┌─────┬─────┐         │  [翻譯] [僅萃取術語]      │
│  │☑ EN │☑ VI │         │                         │
│  │☐ TH │☐ JA │         │  來源語言                │
│  │☐ KO │☐ ID │         │  [自動偵測 ▼]            │
│  │☐ 繁中│☐ 簡中│         │                         │
│  └─────┴─────┘         │  翻譯情境                │
│                         │  [自動路由 ▼]            │
│  [展開完整語言列表 ▼]    │                         │
│                         │  PDF 輸出設定             │
│  路由資訊                │  ○ PDF（保留版面）        │
│  HY-MT → EN, VI        │  ○ DOCX（雙語對照）       │
│  Qwen → JA, KO         │                         │
│                         │  ☐ 翻譯頁首頁尾           │
├────────────────────────┴─────────────────────────┤
│  [← 上一步]                   [開始翻譯 ▶]         │
└──────────────────────────────────────────────────┘
```

設計要點：
- **來源語言不再隱藏**：直接以下拉選單呈現，預設「自動偵測」
- **翻譯情境不再隱藏**：直接以下拉選單呈現，預設「自動路由」
- **PDF 設定條件顯示**：只有已選檔案包含 PDF 時才顯示 PDF 相關選項
- **路由資訊即時顯示**：選完目標語言後，在下方以小字顯示系統將使用的模型路由
- **VRAM 計算移至「設定」頁面**：不在翻譯流程中干擾使用者

#### 步驟三：翻譯進度與下載

```
┌──────────────────────────────────────────────────┐
│  翻譯狀態                          [翻譯中... ●]   │
│                                                   │
│  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░  47%             │
│                                                   │
│  目前翻譯：report.docx [Vietnamese]               │
│  段落進度：23 / 48                                 │
│                                                   │
│  ┌──────────┬──────────┬──────────┬──────────┐    │
│  │ 檔案進度  │ 段落進度  │ 速度     │ 預估剩餘  │    │
│  │ 1/3      │ 23/142   │ 2.1/秒  │ 3分12秒  │    │
│  └──────────┴──────────┴──────────┴──────────┘    │
│                                                   │
│  ┌───────────────────────────────────────────┐    │
│  │ 個別檔案進度                                │    │
│  │ report.docx   ▓▓▓▓▓▓▓▓░░  80%  [VI]     │    │
│  │ data.xlsx     ▓▓▓░░░░░░░  30%  [EN]     │    │
│  │ slides.pptx   ░░░░░░░░░░   0%  等待中    │    │
│  └───────────────────────────────────────────┘    │
│                                                   │
│  術語萃取結果（完成時顯示）                         │
│  萃取 12 筆 / 新增 8 筆 / 略過 4 筆                │
│                                                   │
│                    [取消翻譯 ■]                     │
│  （完成後變為）                                     │
│  [下載全部檔案 ↓]  [開始新翻譯 ↻]                   │
└──────────────────────────────────────────────────┘
```

設計要點：
- **個別檔案進度**：每個檔案獨立顯示進度條和目前處理的語言
- **統計數據用卡片式排列**：檔案進度、段落進度、速度、剩餘時間各一張小卡
- **術語萃取結果**：翻譯完成後自動顯示術語萃取摘要，附帶「前往術語庫審核」連結
- **錯誤訊息**：翻譯失敗時，以醒目的紅色警告區塊顯示，取代 alert()

### 2.2 術語庫管理 (`/terms`)

從滑出式面板升級為**完整頁面**，採用頁籤式導覽。

```
┌──────────────────────────────────────────────────┐
│  術語庫管理                                       │
│  [總覽] [待審核 (5)] [已核准] [匯入匯出]            │
├──────────────────────────────────────────────────┤
```

#### 總覽頁籤

```
┌───────────────┬───────────────┬───────────────┐
│  總術語數      │  待審核        │  已核准        │
│    156         │     5          │    151         │
│                │  需要您的注意   │                │
└───────────────┴───────────────┴───────────────┘

┌──────────────────────┬───────────────────────────┐
│  依目標語言            │  依領域                    │
│  ┌─────────────────┐  │  ┌───────────────────┐    │
│  │ English    62   │  │  │ 技術製程      89   │    │
│  │ Vietnamese 45   │  │  │ 商務金融      42   │    │
│  │ Japanese   28   │  │  │ 法律合約      15   │    │
│  │ ...             │  │  │ ...                │    │
│  └─────────────────┘  │  └───────────────────┘    │
└──────────────────────┴───────────────────────────┘
```

#### 待審核頁籤 (`/terms/review`)

```
┌──────────────────────────────────────────────────┐
│  篩選：[語言 ▼] [領域 ▼] [搜尋...]     [全部核准]   │
├──────────────────────────────────────────────────┤
│                                                   │
│  ┌─────────────────────────────────────────────┐  │
│  │ semiconductor → 半導體                       │  │
│  │ 領域：技術製程 · 目標語言：繁體中文 · 信心值：87% │  │
│  │ 上下文：「...semiconductor fabrication...」   │  │
│  │                        [編輯] [核准 ✓]       │  │
│  ├─────────────────────────────────────────────┤  │
│  │ yield rate → 良率                            │  │
│  │ ...                                          │  │
│  └─────────────────────────────────────────────┘  │
│                                                   │
│  [顯示更多...]                                    │
└──────────────────────────────────────────────────┘
```

設計要點：
- 每個術語佔一個卡片行，資訊層次清楚：原文 → 譯文（大字）、後設資料（小字）、操作按鈕（右側）
- 支援篩選器：按語言、領域篩選
- 搜尋框支援即時搜尋
- 批次操作：勾選多筆後可一次核准
- 行內編輯：點擊譯文可直接修改

#### 已核准頁籤

與待審核類似，但操作按鈕為「編輯」、且顯示使用次數。支援排序（按使用次數、字母順序、最近修改）。

#### 匯入匯出頁籤

```
┌──────────────────────┬───────────────────────────┐
│  匯出                 │  匯入                      │
│                       │                            │
│  匯出範圍              │  選擇檔案                   │
│  [全部 ▼]             │  [選擇檔案] data.csv        │
│                       │                            │
│  匯出格式              │  衝突策略                   │
│  [JSON] [CSV] [XLSX]  │  ○ 保留現有 (skip)          │
│                       │  ○ 覆蓋未核准 (overwrite)   │
│                       │  ○ 依信心值合併 (merge)      │
│                       │  ○ 強制覆蓋 (force)          │
│                       │                            │
│                       │  [確認匯入]                  │
│                       │                            │
│                       │  匯入結果：                  │
│                       │  新增 12 / 略過 3 / 覆蓋 2  │
└──────────────────────┴───────────────────────────┘
```

### 2.3 設定中心 (`/settings`)

所有設定從隱藏的折疊面板中解放，改為完整頁面，按類別分區。

```
┌──────────────────────────────────────────────────┐
│  設定                                             │
├──────────────────────────────────────────────────┤
│                                                   │
│  ┌─ 系統狀態 ────────────────────────────────┐    │
│  │  Ollama 連線：● 已連線 (v0.3.12)           │    │
│  │  可用模型：HY-MT, Qwen2.5-7B               │    │
│  │  GPU：NVIDIA RTX 3060 (8 GB)              │    │
│  │  快取：127 筆 / 2.3 MB                     │    │
│  │                       [清除快取]            │    │
│  └────────────────────────────────────────────┘    │
│                                                   │
│  ┌─ GPU 與記憶體 ────────────────────────────┐    │
│  │  GPU VRAM 容量                             │    │
│  │  [8 GB ▼]                                  │    │
│  │                                            │    │
│  │  上下文長度 (num_ctx)                       │    │
│  │  ◄━━━━━━━━━━●━━━━━━━━━━►  3072             │    │
│  │  1024              8192                    │    │
│  │                                            │    │
│  │  VRAM 使用率估算                            │    │
│  │  ▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░  68%               │    │
│  │  模型 5.7 GB + KV Cache 0.7 GB = 6.4 GB   │    │
│  └────────────────────────────────────────────┘    │
│                                                   │
│  ┌─ 翻譯預設值 ──────────────────────────────┐    │
│  │  預設來源語言：[自動偵測 ▼]                  │    │
│  │  預設翻譯情境：[自動路由 ▼]                  │    │
│  │  預設目標語言：[☑ EN] [☑ VI] [☐ JA]...     │    │
│  │  翻譯頁首頁尾（僅限 Windows）：[開關]        │    │
│  └────────────────────────────────────────────┘    │
│                                                   │
│  ┌─ PDF 輸出設定 ────────────────────────────┐    │
│  │  預設輸出格式：○ PDF（保留版面） ○ DOCX     │    │
│  │  PDF 版面模式：○ 覆蓋模式 ○ 並排模式        │    │
│  └────────────────────────────────────────────┘    │
│                                                   │
│  ┌─ 介面 ────────────────────────────────────┐    │
│  │  外觀模式：[淺色] [暗色] [跟隨系統]          │    │
│  │  介面語言：[繁體中文 ▼]                     │    │
│  └────────────────────────────────────────────┘    │
│                                                   │
└──────────────────────────────────────────────────┘
```

設計要點：
- **系統狀態區塊**最顯眼，呼叫 `/api/health` 和 `/api/cache/stats` 取得即時資訊
- **GPU 與記憶體**：將 VRAM 計算器從進階設定提升為獨立區塊
- **翻譯預設值**：設定預設語言、情境等，啟動翻譯時自動帶入
- **快取管理**：顯示快取統計並提供清除按鈕（呼叫 `DELETE /api/cache`）

### 2.4 翻譯歷史 (`/history`)

```
┌──────────────────────────────────────────────────┐
│  翻譯歷史                                        │
│  [篩選：全部 ▼]  [搜尋檔名...]                     │
├──────────────────────────────────────────────────┤
│                                                   │
│  ┌─ 2026-03-10 ──────────────────────────────┐   │
│  │                                            │   │
│  │  Job abc123...                             │   │
│  │  3 個檔案 → English, Vietnamese            │   │
│  │  情境：自動路由                              │   │
│  │  狀態：✓ 完成 · 耗時 4分32秒                 │   │
│  │  [重新下載] [以相同設定再翻譯]                 │   │
│  │                                            │   │
│  ├────────────────────────────────────────────┤   │
│  │  Job def456...                             │   │
│  │  1 個檔案 → Japanese                       │   │
│  │  狀態：✗ 失敗（模型載入逾時）                  │   │
│  │                                            │   │
│  └────────────────────────────────────────────┘   │
│                                                   │
│  統計摘要                                         │
│  本月翻譯：23 個工作 · 67 個檔案 · 12,340 段落     │
│  快取命中率：34%                                   │
│                                                   │
└──────────────────────────────────────────────────┘
```

注意：目前後端沒有持久化的歷史紀錄 API。此頁面初期可使用前端 localStorage 儲存最近 50 筆工作紀錄（Job ID、檔案名稱、目標語言、狀態、時間戳），待後端擴充後改用 API。

---

## 3. 元件庫規劃

### 3.1 基礎元件 (Primitives)

| 元件 | 說明 | 變體 |
|------|------|------|
| `Button` | 基礎按鈕 | `primary`, `secondary`, `danger`, `success`, `ghost` / 尺寸 `xs`, `sm`, `md`, `lg` |
| `IconButton` | 只有圖示的按鈕 | 同上變體 |
| `Input` | 文字輸入框 | 附帶 label、錯誤訊息、前綴/後綴圖示 |
| `Select` | 下拉選單 | 單選、原生 `<select>` 封裝 |
| `Checkbox` | 核取方塊 | 含自訂打勾圖示 |
| `Radio` | 單選按鈕 | 含說明文字的卡片式變體 |
| `Toggle` | 開關切換 | 含標籤 |
| `Slider` | 範圍滑桿 | 含最小/最大標記、目前值顯示 |
| `Badge` | 標籤/徽章 | `info`, `success`, `warning`, `error`, `neutral` |
| `Tooltip` | 提示文字 | 上/下/左/右方向 |

### 3.2 回饋元件 (Feedback)

| 元件 | 說明 |
|------|------|
| `Toast` / `Notification` | 取代 `alert()` 的通知系統，支援 `success`, `error`, `warning`, `info` 四種類型，自動消失（可設定秒數），堆疊顯示於右上角 |
| `ProgressBar` | 進度條，支援條紋動畫（進行中）、顏色變化（正常/警告/錯誤） |
| `StatusDot` | 狀態圓點指示器（綠/黃/紅），用於 Ollama 連線狀態 |
| `Spinner` | 載入旋轉器 |
| `EmptyState` | 空狀態插圖 + 文字 + 行動按鈕 |
| `ErrorBoundary` | 全域錯誤捕捉元件，顯示友善的錯誤訊息 |
| `Skeleton` | 骨架螢幕載入狀態 |

### 3.3 佈局元件 (Layout)

| 元件 | 說明 |
|------|------|
| `AppShell` | 應用程式外殼：側邊欄 + 頂部列 + 主內容區 |
| `Sidebar` | 側邊導覽列，含圖示+文字，底部固定系統狀態區 |
| `TopBar` | 頂部列：麵包屑 + 動作區 |
| `Card` | 卡片容器，含 header、body、footer 插槽 |
| `PageHeader` | 頁面標題列，含標題、描述、動作按鈕 |
| `Tabs` | 頁籤元件，支援徽章計數器 |
| `Divider` | 分隔線 |

### 3.4 業務元件 (Domain-specific)

| 元件 | 說明 |
|------|------|
| `FileDropZone` | 檔案拖放上傳區域 |
| `FileCard` | 檔案資訊卡片（圖示、名稱、大小、移除按鈕） |
| `FileList` | 檔案列表（含標題列、清除全部） |
| `LanguageGrid` | 常用目標語言核取方塊格子 |
| `LanguageSelector` | 完整語言選擇器（含搜尋、分組） |
| `StepWizard` | 精靈式步驟指示器（可點擊導航） |
| `TranslationProgress` | 翻譯進度監控面板 |
| `StatusBadge` | 工作狀態標記（idle/running/completed/failed） |
| `TermCard` | 術語卡片（原文、譯文、後設資料、操作按鈕） |
| `TermTable` | 術語列表/表格（含篩選、排序、分頁） |
| `VramCalculator` | VRAM 使用率計算器 |
| `RouteInfoDisplay` | 模型路由資訊顯示 |
| `HealthIndicator` | Ollama 健康狀態指示器（側邊欄） |

### 3.5 圖示系統

將目前 15+ 個內嵌 SVG 抽離為獨立的圖示元件系統：

```
src/components/icons/
├── index.js          (統一匯出)
├── Check.jsx
├── Upload.jsx
├── Cloud.jsx
├── Globe.jsx
├── Settings.jsx
├── ...
```

建議改用 `lucide-react` 圖示庫，它提供：
- 與目前內嵌 SVG 風格一致的線條圖示
- 樹搖動（tree-shaking）支援，不增加多餘體積
- 統一的 API（`<Icon size={20} strokeWidth={2} />`）

---

## 4. 互動流程

### 4.1 翻譯主工作流程

```
[進入翻譯工作台]
        │
        ▼
┌─ 步驟 1：上傳 ──────────────────────────────────┐
│  使用者拖放或選擇檔案                               │
│  → 檔案出現在列表中（帶入場動畫）                     │
│  → 「下一步」按鈕亮起                               │
│  → 點擊「下一步」或自動切換至步驟 2                   │
└──────────────────────────────────────────────────┘
        │ 至少 1 個檔案
        ▼
┌─ 步驟 2：語言與設定 ─────────────────────────────┐
│  預設帶入上次使用的目標語言                           │
│  勾選/取消勾選目標語言                               │
│  → 路由資訊即時更新                                 │
│  （可選）調整來源語言、翻譯情境                       │
│  （可選）調整 PDF 設定                              │
│  → 點擊「開始翻譯」或「開始萃取」                     │
└──────────────────────────────────────────────────┘
        │ 送出 API 請求
        ▼
┌─ 步驟 3：進度與下載 ─────────────────────────────┐
│  自動輪詢 Job 狀態（每 2 秒）                       │
│  進度條即時更新                                     │
│  個別檔案進度更新                                   │
│  ├─ 翻譯中 → 顯示「取消」按鈕                       │
│  ├─ 完成 → 顯示「下載」按鈕 + 術語萃取摘要           │
│  │         → Toast 通知「翻譯完成」                 │
│  │         → 儲存紀錄至 localStorage                │
│  ├─ 失敗 → 顯示錯誤訊息 + Toast 通知               │
│  └─ 取消 → 顯示已取消狀態                           │
│                                                   │
│  完成後：[下載全部] [開始新翻譯]                      │
└──────────────────────────────────────────────────┘
```

**狀態轉換規則**：
- 步驟 1 → 2：至少選取一個檔案
- 步驟 2 → 3：至少勾選一個目標語言 + 點擊開始
- 步驟 3 → 1：點擊「開始新翻譯」重置所有狀態
- 步驟指示器可任意點擊回到前面步驟（但進入步驟 3 後鎖定，翻譯進行中不可回退）

### 4.2 術語審核流程

```
[進入術語庫] → [待審核頁籤]
        │
        ▼
┌─ 瀏覽待審核術語 ──────────────────────────────────┐
│  每個術語卡片顯示：                                  │
│  原文 → 譯文 · 領域 · 語言 · 信心值 · 上下文片段     │
│                                                   │
│  操作：                                            │
│  ├─ [核准]：確認術語正確                             │
│  │  → 術語從列表消失（帶出場動畫）                     │
│  │  → Toast 通知「已核准」                           │
│  │  → 待審核計數器 -1                               │
│  │                                                 │
│  ├─ [編輯]：修改譯文後核准                            │
│  │  → 行內展開編輯框                                 │
│  │  → Enter 儲存 / Escape 取消                      │
│  │                                                 │
│  └─ [全部核准]：批次核准（附確認對話框）                │
└──────────────────────────────────────────────────┘
```

### 4.3 通知系統行為

取代所有 `alert()` 呼叫，Toast 通知系統的行為規則：

| 事件 | 類型 | 持續時間 | 訊息範例 |
|------|------|----------|---------|
| 翻譯完成 | success | 5 秒 | 「翻譯完成，共 3 個檔案已就緒」 |
| 翻譯失敗 | error | 不自動消失 | 「翻譯失敗：模型載入逾時」 |
| 術語核准成功 | success | 3 秒 | 「術語已核准：semiconductor → 半導體」 |
| 術語核准失敗 | error | 5 秒 | 「核准失敗：{錯誤訊息}」 |
| 術語匯入完成 | success | 5 秒 | 「匯入完成：新增 12 筆、略過 3 筆」 |
| 快取已清除 | info | 3 秒 | 「翻譯快取已清除」 |
| Ollama 離線 | warning | 不自動消失 | 「Ollama 服務未回應，請確認已啟動」 |
| 檔案格式不支援 | warning | 4 秒 | 「已略過不支援的檔案：readme.txt」 |

---

## 5. 視覺設計方向

### 5.1 設計語言

保留現有的 Design Token 系統（CSS 自訂屬性），在此基礎上擴充。整體風格定調為**工具型專業介面** -- 乾淨、效率、低干擾。參考 Linear、Notion、Vercel Dashboard 的視覺語言。

### 5.2 色彩系統擴充

保留現有的色彩 Token 不變（`--primary-*`, `--neutral-*`, `--success`, `--warning`, `--error`, `--info`），新增暗色模式 Token：

```css
/* 新增：暗色模式語義色彩 */
[data-theme="dark"] {
  --bg-primary: #0f1117;
  --bg-secondary: #161922;
  --bg-tertiary: #1e2130;
  --bg-gradient: linear-gradient(135deg, #3b3f8c 0%, #5b3a7a 100%);

  --surface-elevated: #1e2130;
  --surface-overlay: rgba(0, 0, 0, 0.7);

  --border-light: #2a2d3a;
  --border-default: #3a3d4a;
  --border-dark: #4a4d5a;

  --text-primary: #e8eaed;
  --text-secondary: #9aa0a6;
  --text-tertiary: #6b7280;
  --text-muted: #5f6368;
  --text-inverse: #0f1117;

  --shadow-sm: 0 1px 3px 0 rgba(0, 0, 0, 0.3);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.4);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.5);
}
```

**暗色模式切換方式**：在 `<html>` 元素設定 `data-theme="dark"` 屬性，所有元件自動適應。提供三個選項：淺色 / 暗色 / 跟隨系統（`prefers-color-scheme`）。

### 5.3 排版規則

保留現有的 Inter 字型系統，補充 CJK 字型堆疊：

```css
--font-sans: 'Inter', 'Noto Sans TC', -apple-system, BlinkMacSystemFont,
             'Segoe UI', Roboto, 'Microsoft JhengHei', sans-serif;
```

排版層級：
- **頁面標題** (h1)：`--text-2xl` (1.5rem), `font-weight: 700`
- **區塊標題** (h2)：`--text-lg` (1.125rem), `font-weight: 600`
- **卡片標題** (h3)：`--text-base` (1rem), `font-weight: 600`
- **正文**：`--text-sm` (0.875rem), `font-weight: 400`
- **輔助文字**：`--text-xs` (0.75rem), `color: var(--text-muted)`
- **等寬/技術數據**：`--font-mono`（Job ID、VRAM 數值等）

### 5.4 間距規則

使用現有的 `--space-*` Token，補充使用指引：

| 層級 | 間距 | 應用場景 |
|------|------|---------|
| 緊湊 | `--space-1` ~ `--space-2` | 相關元素之間（圖示與文字、標籤與輸入框） |
| 標準 | `--space-3` ~ `--space-4` | 同一區塊內的元素間距 |
| 寬鬆 | `--space-5` ~ `--space-6` | 不同區塊之間、卡片內距 |
| 區段 | `--space-8` ~ `--space-12` | 頁面不同區段之間 |

### 5.5 動效規則

使用現有的 `--transition-*` Token：

| 動效 | 應用 |
|------|------|
| `--transition-fast` (150ms) | 按鈕 hover、核取方塊切換、tooltips |
| `--transition-normal` (250ms) | 卡片出入場、頁籤切換、側邊欄展開收合 |
| `--transition-slow` (350ms) | 頁面路由切換（淡入淡出） |

新增動效：
- **術語核准**：卡片向右滑出 + 淡出（300ms）
- **檔案新增**：卡片從下方滑入 + 淡入（200ms）
- **Toast 通知**：從右側滑入（250ms），消失時向上淡出（200ms）
- **進度條**：使用 CSS `transition: width 500ms ease` 平滑過渡

### 5.6 側邊欄設計

```
寬度：240px（展開）/ 64px（收合）
背景：var(--bg-primary)，與主內容區有邊框分隔
導覽項目：
  - 每項 44px 高（觸控友善）
  - 左側 24px 圖示 + 文字
  - 選中狀態：左側 3px 藍色邊條 + 背景 var(--primary-50)
  - hover 狀態：背景 var(--bg-secondary)
```

---

## 6. 響應式策略

### 6.1 斷點定義

```css
/* 保留既有斷點，新增補充 */
--bp-mobile: 480px;    /* 手機（低優先） */
--bp-tablet: 768px;    /* 平板 */
--bp-desktop: 1024px;  /* 桌面（主要） */
--bp-wide: 1400px;     /* 寬螢幕 */
```

### 6.2 佈局行為

| 斷點 | 側邊欄 | 主內容區 | 步驟指示器 |
|------|--------|---------|-----------|
| >= 1024px (桌面) | 240px 固定 | 剩餘空間，最大 1200px | 水平展開 |
| 768-1023px (平板) | 64px 圖示模式 | 剩餘空間 | 水平展開，省略描述文字 |
| < 768px (手機) | 底部導覽列 (56px) | 全寬 | 隱藏，改用頁面頂部文字「步驟 2/3」 |

### 6.3 頁面層級響應式行為

**翻譯工作台 - 步驟二（語言與設定）**：
- 桌面：左右分欄（語言 / 設定）
- 平板/手機：上下堆疊（語言在上、設定在下）

**術語庫 - 術語卡片**：
- 桌面：原文 → 譯文 水平排列，操作按鈕在右側
- 平板/手機：原文 → 譯文 垂直堆疊，操作按鈕在底部

**設定中心**：
- 桌面：雙欄卡片佈局（系統狀態 + GPU / 翻譯預設 + PDF 設定）
- 平板/手機：單欄堆疊

### 6.4 側邊欄收合邏輯

- 桌面預設展開，使用者可手動切換收合
- 平板預設收合為圖示模式，hover 時暫時展開
- 手機不顯示側邊欄，改用底部固定導覽列（4 個項目：翻譯、術語庫、歷史、設定）

---

## 7. 技術架構建議

### 7.1 新增依賴

```json
{
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.28.0",
    "lucide-react": "^0.460.0",
    "sonner": "^1.7.0"
  }
}
```

| 套件 | 用途 | 理由 |
|------|------|------|
| `react-router-dom` | 客戶端路由 | 行業標準，支援巢狀路由、lazy loading |
| `lucide-react` | 圖示系統 | 取代 15+ 個內嵌 SVG，風格一致、tree-shakeable，壓縮後 ~5KB |
| `sonner` | Toast 通知 | 輕量 (~3KB)、美觀、支援堆疊，取代所有 `alert()` |

**刻意不使用的套件**：
- 不使用 Tailwind CSS：保留現有 CSS 自訂屬性系統，避免大量重構
- 不使用 Redux/Zustand：應用規模不需要全域狀態管理庫，React Context + useReducer 足夠
- 不使用 UI 元件庫（MUI、Ant Design）：保持客製化控制，且現有 Design Token 已足夠完善
- 不使用 React Query/SWR：API 呼叫數量有限，手動管理即可

### 7.2 資料夾結構

```
app/frontend/src/
├── main.jsx                    # 入口，掛載 Router
├── App.jsx                     # Router 定義 + AppShell 佈局
│
├── components/                 # 可重用元件
│   ├── ui/                     # 基礎 UI 元件
│   │   ├── Button.jsx
│   │   ├── Button.css
│   │   ├── Card.jsx
│   │   ├── Card.css
│   │   ├── Input.jsx
│   │   ├── Select.jsx
│   │   ├── Checkbox.jsx
│   │   ├── Radio.jsx
│   │   ├── Toggle.jsx
│   │   ├── Slider.jsx
│   │   ├── Badge.jsx
│   │   ├── Tabs.jsx
│   │   ├── ProgressBar.jsx
│   │   ├── Tooltip.jsx
│   │   ├── Skeleton.jsx
│   │   └── EmptyState.jsx
│   │
│   ├── layout/                 # 佈局元件
│   │   ├── AppShell.jsx        # 側邊欄 + 頂部列 + 主內容
│   │   ├── AppShell.css
│   │   ├── Sidebar.jsx
│   │   ├── TopBar.jsx
│   │   └── PageHeader.jsx
│   │
│   ├── feedback/               # 回饋元件
│   │   ├── StatusDot.jsx
│   │   ├── ErrorBoundary.jsx
│   │   └── Spinner.jsx
│   │
│   └── domain/                 # 業務元件
│       ├── FileDropZone.jsx
│       ├── FileDropZone.css
│       ├── FileCard.jsx
│       ├── FileList.jsx
│       ├── LanguageGrid.jsx
│       ├── LanguageSelector.jsx
│       ├── StepWizard.jsx
│       ├── StepWizard.css
│       ├── TranslationProgress.jsx
│       ├── StatusBadge.jsx
│       ├── TermCard.jsx
│       ├── TermTable.jsx
│       ├── VramCalculator.jsx
│       ├── RouteInfoDisplay.jsx
│       └── HealthIndicator.jsx
│
├── pages/                      # 頁面元件
│   ├── TranslatePage.jsx       # 翻譯工作台（精靈流程）
│   ├── TranslatePage.css
│   ├── TermsPage.jsx           # 術語庫總覽
│   ├── TermsPage.css
│   ├── TermsReviewPage.jsx     # 術語審核
│   ├── SettingsPage.jsx        # 設定中心
│   ├── SettingsPage.css
│   └── HistoryPage.jsx         # 翻譯歷史
│
├── hooks/                      # 自訂 Hooks
│   ├── useJobPolling.js        # 工作狀態輪詢（取代 App.jsx 的 useEffect）
│   ├── useHealthCheck.js       # Ollama 健康檢查（定期呼叫 /api/health）
│   ├── useLocalStorage.js      # localStorage 讀寫封裝
│   ├── useTheme.js             # 暗色模式切換
│   └── useNotification.js      # 通知系統 hook（封裝 sonner）
│
├── contexts/                   # React Context
│   ├── SettingsContext.jsx      # 全域設定（VRAM、預設語言、主題等）
│   └── NotificationContext.jsx  # 通知佇列（若 sonner 不夠用）
│
├── api/                        # API 層
│   ├── client.js               # 基礎 fetch 封裝（錯誤處理、base URL）
│   ├── jobs.js                 # 翻譯工作 API
│   ├── terms.js                # 術語庫 API
│   ├── system.js               # 健康檢查、快取、統計 API
│   └── config.js               # 模型設定、翻譯情境 API
│
├── constants/                  # 常數定義
│   ├── languages.js            # 語言列表、分組
│   ├── fileTypes.js            # 檔案類型定義
│   └── defaults.js             # 預設值（模型設定、VRAM 選項等）
│
├── i18n/                       # 國際化
│   ├── index.js                # i18n 系統（輕量級，不使用 i18next）
│   ├── zh-TW.js                # 繁體中文（預設）
│   └── en.js                   # 英文（備用）
│
└── styles/                     # 全域樣式
    ├── tokens.css              # 設計 Token（從現有 styles.css 遷移）
    ├── reset.css               # CSS Reset
    ├── base.css                # 基礎樣式（body、typography）
    ├── utilities.css           # 工具類（sr-only、truncate 等）
    └── theme-dark.css          # 暗色模式覆蓋
```

### 7.3 狀態管理策略

**不使用全域狀態管理庫**。使用以下分層策略：

| 狀態層級 | 方案 | 範例 |
|---------|------|------|
| **頁面內部狀態** | `useState` / `useReducer` | 翻譯精靈的步驟、檔案列表、語言選擇 |
| **跨頁面共享設定** | `React Context` | 主題模式、GPU VRAM、預設語言（持久化至 localStorage） |
| **伺服器資料** | 自訂 Hook（含 fetch + 狀態） | `useHealthCheck()`, `useJobPolling(jobId)` |
| **持久化資料** | `localStorage` | 翻譯歷史紀錄、使用者偏好設定 |

**翻譯工作台的狀態用 `useReducer` 管理**，取代目前 20+ 個獨立 useState：

```javascript
// 概念範例（不需要實作）
const initialState = {
  step: 0,                    // 0=上傳, 1=設定, 2=翻譯
  files: [],
  targetLanguages: [],
  srcLang: 'auto',
  profile: 'auto',
  pdfOutputFormat: 'pdf',
  pdfLayoutMode: 'overlay',
  includeHeaders: false,
  jobMode: 'translation',
  jobId: null,
  jobStatus: null,
  error: null,
  loading: false,
};

function reducer(state, action) {
  switch (action.type) {
    case 'ADD_FILES': ...
    case 'REMOVE_FILE': ...
    case 'SET_TARGETS': ...
    case 'NEXT_STEP': ...
    case 'PREV_STEP': ...
    case 'START_JOB': ...
    case 'UPDATE_STATUS': ...
    case 'RESET': ...
  }
}
```

### 7.4 API 層重構

將現有的 `api.js` 單一檔案拆分，並增加統一的錯誤處理：

```javascript
// api/client.js 概念
async function request(url, options = {}) {
  const res = await fetch(url, options);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const error = new Error(body.detail || `Request failed: ${res.status}`);
    error.status = res.status;
    throw error;
  }
  return res.json();
}
```

新增目前未使用的 API 呼叫：
- `GET /api/health` → 定期健康檢查（每 30 秒）
- `GET /api/stats` → 翻譯歷史統計
- `GET /api/cache/stats` → 快取統計
- `DELETE /api/cache` → 清除快取
- `POST /api/terms/wikidata/search` → Wikidata 術語搜尋（未來擴充）

### 7.5 國際化策略

不引入重型 i18n 框架，用簡單的 key-value 方案：

```javascript
// i18n/zh-TW.js
export default {
  nav: {
    translate: '翻譯',
    terms: '術語庫',
    history: '歷史紀錄',
    settings: '設定',
  },
  translate: {
    uploadTitle: '上傳文件',
    uploadDesc: '將檔案或資料夾拖放至此',
    selectFiles: '選擇檔案',
    selectFolder: '選擇資料夾',
    nextStep: '下一步',
    prevStep: '上一步',
    startTranslation: '開始翻譯',
    startExtraction: '開始萃取',
    // ...
  },
  // ...
};
```

介面預設語言為繁體中文。英文作為備用（部分技術用語保留英文顯示，如 Job ID、VRAM、num_ctx）。

### 7.6 遷移策略

建議分階段遷移，每階段可獨立測試與部署：

**第一階段：基礎架構**
1. 安裝 react-router-dom、lucide-react、sonner
2. 建立資料夾結構
3. 遷移 CSS Token 至 `styles/tokens.css`
4. 建立 AppShell 佈局（側邊欄 + 頂部列）
5. 設定路由
6. 建立基礎 UI 元件（Button、Card、Input 等）

**第二階段：翻譯工作台**
1. 將翻譯流程拆為 TranslatePage 和步驟子元件
2. 實作 StepWizard 可點擊導航
3. 遷移 FileDropZone、FileCard、LanguageGrid
4. 用 useReducer 取代 20+ 個 useState
5. 接入通知系統取代 alert()

**第三階段：術語庫**
1. 建立 TermsPage 和 TermsReviewPage
2. 遷移 TermDBPanel 的邏輯至頁面元件
3. 新增篩選、搜尋、批次操作功能

**第四階段：設定與歷史**
1. 建立 SettingsPage，整合所有設定
2. 接入 /api/health、/api/cache/stats 等 API
3. 建立 HistoryPage（localStorage 方案）
4. 實作暗色模式

**第五階段：精修**
1. 國際化文案統一
2. 動效打磨
3. 無障礙稽核（鍵盤導航、ARIA 標籤、對比度）
4. 效能最佳化（lazy loading 頁面元件）

---

## 附錄：現有程式碼對應表

| 現有程式碼 | 遷移目標 |
|-----------|---------|
| `App.jsx` 第 1-50 行（常數定義） | `constants/languages.js`, `constants/fileTypes.js`, `constants/defaults.js` |
| `App.jsx` 第 84-199 行（Icons 物件） | 刪除，改用 `lucide-react` |
| `App.jsx` 第 202-260 行（StepIndicator, ProgressBar, StatusBadge） | `components/domain/StepWizard.jsx`, `components/ui/ProgressBar.jsx`, `components/domain/StatusBadge.jsx` |
| `App.jsx` 第 282-427 行（FileCard, LanguageSelector） | `components/domain/FileCard.jsx`, `components/domain/LanguageSelector.jsx` |
| `App.jsx` 第 445-754 行（TermDBPanel） | `pages/TermsPage.jsx`, `pages/TermsReviewPage.jsx` |
| `App.jsx` 第 757-930 行（App 元件 state + effects） | `pages/TranslatePage.jsx` + `hooks/useJobPolling.js` |
| `App.jsx` 第 1115-1730 行（JSX 渲染） | 分散至各頁面元件 |
| `api.js` | `api/client.js`, `api/jobs.js`, `api/terms.js`, `api/system.js`, `api/config.js` |
| `styles.css` 第 1-135 行（Token） | `styles/tokens.css` + `styles/theme-dark.css` |
| `styles.css` 第 137-160 行（Reset） | `styles/reset.css` |
| `styles.css` 其餘 | 拆入各元件的 CSS 檔案 |
