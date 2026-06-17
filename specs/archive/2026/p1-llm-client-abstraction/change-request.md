# Change Request

## Original Request

**P1-2 from improvement-plan.md Phase 1:**

新增 `clients/base_llm_client.py`，定義 `LLMClient(Protocol)` 抽象基底（translate_once, translate_batch, refine_translation, health, list_models, unload 六個方法）。

現有 `clients/ollama_client.py` 改為 `OllamaClient(LLMClient)` 實作介面。

`translation_service.py` 改為依賴 `LLMClient` 介面，移除對 `_build_no_system_payload` / `_call_ollama` 私有方法的直接呼叫（痛點 7）。

## Business / User Goal

建立 LLM provider 抽象層，使後續 p1-cloud-providers（OpenAICompatibleClient / Panjit / DeepSeek）可以在不修改 translation_service.py 邏輯的情況下直接插入。

## Non-goals

- 不新增 OpenAICompatibleClient 或任何雲端 provider（由 p1-cloud-providers 處理）
- 不修改 API 路由、schemas、business rules
- 不更改翻譯行為（純粹重構——功能不變）
- 不修改 frontend

## Constraints

- 現有所有翻譯 unit tests 必須繼續通過（regression-free refactor）
- `OllamaClient` 的對外 public API 不能變（不允許 breaking changes）
- 使用 Python `typing.Protocol`（structural subtyping），不引入新的 third-party dependency

## Known Context

- depends-on: p1-contract-baseline（已完成，合約基線已建立）
- 痛點 7：translation_service.py 直接呼叫 `_build_no_system_payload` / `_call_ollama` 私有方法，使其緊耦合到 OllamaClient 的實作細節，無法替換 provider

## Open Questions

- 無

## Requested Delivery Date / Priority

P1 Phase，依 p1-cloud-providers 依賴鏈，儘早完成
