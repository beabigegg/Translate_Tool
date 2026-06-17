# Design: p1-llm-client-abstraction

## Summary
Introduce `LLMClient` as a `typing.Protocol` (structural subtyping) in a new module `app/backend/clients/base_llm_client.py`, defining the six provider-facing methods (`translate_once`, `translate_batch`, `refine_translation`, `health`, `list_models`, `unload`). `OllamaClient` is made a structural subtype by adding three thin alias methods (`health`, `list_models`, `unload`) that delegate to its existing, frozen public methods, while the formerly-private payload logic (`_build_no_system_payload` / `_call_ollama`) stays entirely inside `OllamaClient`. `translation_service.py` and `translation_helpers.py` are rewired to depend only on the Protocol surface, removing every direct call to `OllamaClient` private methods. This is a behavior-preserving dependency-inversion refactor that lets `p1-cloud-providers` plug `OpenAICompatibleClient` / Panjit / DeepSeek into the same consumers without touching the translation path.

## Affected Components
| component | file path(s) | nature of change |
|---|---|---|
| Protocol definition | `app/backend/clients/base_llm_client.py` (new) | Defines `LLMClient(Protocol)` + 6 method signatures; stdlib `typing.Protocol` only |
| Ollama implementation | `app/backend/clients/ollama_client.py` | Add `health`/`list_models`/`unload` aliases; keep all existing public + private methods unchanged; structurally conforms to `LLMClient` |
| Translation service | `app/backend/services/translation_service.py` | Type hints `OllamaClient`→`LLMClient`; replace direct `_build_no_system_payload`/`_call_ollama`/`unload_model` calls with Protocol methods |
| Translation helpers | `app/backend/utils/translation_helpers.py` | Type hints→`LLMClient`; replace `client._is_translation_dedicated()` private call |
| Clients package | `app/backend/clients/__init__.py` | Re-export `LLMClient` (currently empty) |

## Key Decisions

**Protocol surface = consumer contract, not full OllamaClient API.** The Protocol covers exactly the six methods the consumers (`translation_service.py`, `translation_helpers.py`) need to drive a provider. The 30+ Ollama-specific helpers (`_build_*_prompt`, `_call_ollama`, `_smart_retry`, `_parse_batch_response`, etc.) stay private to `OllamaClient` and are absent from the Protocol. Rejected alternative: mirroring the whole public surface (`cache_model_key`, `system_prompt`, `set_runtime_options_override`) into the Protocol — rejected because those are orchestration/config concerns set by `orchestrator.py` (out of scope here), and forcing every future cloud provider to expose Ollama VRAM/cache internals would leak the abstraction.

**Name resolution: add aliases, do not rename.** The improvement-plan names `health`/`list_models`/`unload`, but the frozen public API is `health_check()` (called in `docx_processor.py`), module-level `list_ollama_models()` (called in `routes.py`), and `unload_model()` (called in `resource_utils.py` and `translation_service.py`). AC-4 forbids renaming. Decision: add three thin instance methods delegating to existing behavior — `health`→`health_check`, `unload`→`unload_model`, and `list_models` wraps module-level `list_ollama_models(self.base_url)`. Old names remain. Rejected alternative: rename + leave deprecated shims — rejected as needless public-API churn the regression suite and contract-reviewer would flag.

**Private payload logic stays inside OllamaClient.** The deferred-context-detection block in `translation_service.py` (currently `refine_client._build_no_system_payload(...)` then `refine_client._call_ollama(...)`) is the only consumer reach-through into Ollama internals. That two-step "raw prompt → model response, no system prompt" need is generic, so it is satisfied through an existing Protocol method rather than a new private hook: the context-detection prompt is issued via the public `translate_once`-style flow. The Ollama-specific no-system payload construction remains a private detail invoked only from `OllamaClient`'s own public methods. `translation_helpers.py`'s `client._is_translation_dedicated()` branch is likewise removed; the dedicated-vs-general routing is already internal to `OllamaClient.translate_batch`/`translate_once`, so the helper relies on those public methods instead.

**unload is a no-op for cloud clients.** The Protocol documents `unload` as best-effort VRAM eviction returning `(ok, message)`. Cloud providers implement it as immediate `(True, "no-op")`; `OllamaClient.unload` delegates to real `unload_model`. This keeps the Phase-2 refiner hand-off in `translation_service.py` provider-agnostic.

**Injection stays parameter-based.** Consumers receive the client as a function parameter (`translate_texts(..., client, ..., refine_client=...)`), constructed by `orchestrator.py`. No constructor or module-level injection is introduced — only the parameter *type* changes from `OllamaClient` to `LLMClient`. Rejected alternative: a service class holding an injected client — out of scope and a larger blast radius than a Tier-3 refactor warrants.

**Protocol method signatures (derived from current public API):**
| method | signature | returns |
|---|---|---|
| `translate_once` | `(text: str, tgt: str, src_lang: Optional[str])` | `Tuple[bool, str]` |
| `translate_batch` | `(texts: List[str], tgt: str, src_lang: Optional[str])` | `Tuple[bool, List[str]]` |
| `refine_translation` | `(source_text: str, draft: str, tgt: str, src_lang: Optional[str])` | `Tuple[bool, str]` |
| `health` | `()` | `Tuple[bool, str]` |
| `list_models` | `()` | `List[str]` |
| `unload` | `()` | `Tuple[bool, str]` |

## Import Graph
`base_llm_client.py` imports only stdlib `typing`; it imports nothing from `ollama_client.py` (avoids a cycle — implementation depends on Protocol, never the reverse). `ollama_client.py`, `translation_service.py`, and `translation_helpers.py` import `LLMClient` from `clients.base_llm_client` (or via the `clients` package re-export). Future providers in `p1-cloud-providers` import the same Protocol.

## Migration / Rollback
No data, schema, env, route, or contract migration. The change is additive at the type level: existing `OllamaClient` callers (`routes.py`, `docx_processor.py`, `resource_utils.py`, `orchestrator.py`) keep using the frozen method names and are untouched. Rollback is a pure code revert of the new module and the consumer type/dispatch edits; because no public API was removed and behavior is parity-checked by the existing regression suite, reverting carries no compatibility risk. Validation gate: the full translation regression suite, a Protocol-conformance test asserting `isinstance(OllamaClient(...), LLMClient)` under `runtime_checkable`, and a source-grep test that `translation_service.py` contains zero `_build_no_system_payload`/`_call_ollama` calls.

## Open Risks
- The deferred-context-detection rewrite must reproduce the exact "no system prompt, raw detection prompt" behavior through public methods; if `translate_once` applies sanitization or system-prompt logic the old `_call_ollama` path bypassed, context-detection output could drift. Implementation must confirm parity (covered by `test_hy_mt_quality_refinement.py` plus a targeted conformance test) — flag for `backend-engineer` and `test-strategist`.
- Removing `_is_translation_dedicated()` from `translation_helpers.py` assumes the routing it gated is fully internalized in `OllamaClient.translate_batch`/`translate_once`; verify no consumer-side behavior depended on that branch before deleting.
