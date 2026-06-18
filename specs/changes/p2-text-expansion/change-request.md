# Change Request

## Original Request
P2-4（改善計畫 §4.3.1-2，痛點 11）：在 `renderers/text_region_renderer.py`（312 行）以優先序策略取代現況「縮到約 4pt 直接截斷」：`縮字級 → 縮行距 → 縮字距 → 受控溢出至鄰近空白 → 最後才截斷並標記`，並內建英→德/西/法膨脹係數查表。同時在 `app/backend/utils/font_utils.py` 建立 **metric 相容字型 fallback chain**：目標語言缺字時依 x-height/cap-height/字寬選 metric 相容字型（Noto 為標準 fallback），降低版面位移與 tofu 方框。

## Business / User Goal
解決英→德（+30%）/西（+25%）必爆框與缺字 tofu 兩大版面瑕疵。目標：英→德/西 benchmark 0 爆框、缺字 0 tofu。

## Non-goals
- 不做 CJK 垂直書寫（P3-5）、不做 RTL 鏡像（P3-4）。
- 不做表格框線保護（`p2-table-border-protection`）。
- 不改翻譯內容，只調整渲染呈現。

## Constraints
- 須在 `p2-renderer-convergence` 收斂後的單一 fitz 主路徑 + 共用 bbox 重排上實作，不得在舊雙路徑各做一份。
- 截斷為最後手段，且截斷必須標記（供 QA 安全網 / 人工審查）。
- 字型 fallback 須與既有語言別 Noto 字型載入相容；可結合 P1 的字型 buffer LRU cache。
- 以黃金樣本 + 英→德/西膨脹 benchmark 驗收。

## Known Context
- 前置：`p2-renderer-convergence`
- 渲染器：`app/backend/renderers/text_region_renderer.py`、字型工具：`app/backend/utils/font_utils.py`
- P1 已完成字型 buffer LRU cache（`p1-font-lru-cache`）
- 改善計畫 §4.3、§5.1 風險「文字膨脹 reflow 與原版面衝突」

## Open Questions
- 膨脹係數查表的語對覆蓋範圍（先英→德/西/法，其餘預設係數？）。

## Requested Delivery Date / Priority
P2 軌道 A，Wave 4。前置 `p2-renderer-convergence`。
