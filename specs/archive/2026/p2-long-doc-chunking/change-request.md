# Change Request

## Original Request

長文件語意分塊：對超過 num_ctx token 上限的文件，按語意邊界分塊（段落 / 標題 / 句子）並加 overlap，讓每塊能在單次 LLM 呼叫內完成翻譯；同時建立 Doc2Doc 路徑，使翻譯服務可接受整份文件並自動觸發分塊，不需呼叫端手動切割。

P2-6 from docs/p2-change-requests.md. Depends-on: none (num_ctx splitting already completed in P1).

## Business / User Goal

## Non-goals

## Constraints

## Known Context

## Open Questions

## Requested Delivery Date / Priority
