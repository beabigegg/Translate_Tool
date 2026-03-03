## Context
The translation tool currently sends all instructions via the `prompt` field to Ollama. TranslateGemma is a seq2seq translation model that doesn't support system prompts. Switching to Qwen 3.5 9B (a general-purpose instruct model) unlocks the Ollama `system` field, enabling clean separation of domain instructions from source text.

**Stakeholders**: End users translating semiconductor, manufacturing, and legal documents across Chinese/English/Vietnamese.

## Goals / Non-Goals
- **Goals**:
  - Enable domain-specific translation via selectable profiles
  - Use Ollama `system` field for cleaner prompt architecture
  - Retain internal backward compatibility with translategemma prompt format (profile-internal, not user-facing)
  - Ensure different profiles produce distinct cache entries
  - Preserve existing progress tracking and logging fidelity
  - Keep cache management (clear/stats) functional with new key format
- **Non-Goals**:
  - Custom user-defined profiles (future work)
  - Per-file or per-segment profile switching within a single job
  - Removing translategemma prompt paths (kept as internal fallback for profiles whose `model` field uses translategemma)
  - Exposing a user-facing `model` parameter — model selection is fully delegated to profile resolution
  - Changing the TranslationCache schema or DB migration

## Decisions

### Decision 1: Profiles defined in Python module (not JSON/DB)
Profiles are defined as a `Dict[str, TranslationProfile]` in `app/backend/translation_profiles.py`.
- **Why**: Type-safe, no parsing overhead, easy to add profiles (add dict entry), version-controlled alongside code.
- **Alternatives considered**: JSON file (requires parsing, no type safety), database (overkill, adds complexity for 7 static entries).

### Decision 2: Two-tier prompt architecture (system + user)
The prompt is split into two tiers that map to Ollama API fields:

**System prompt** (`payload["system"]`) — static per job, cached in Ollama KV:
- Persona and role definition (e.g., "You are a professional semiconductor translator")
- Domain-specific terminology glossary and conventions
- Output format rules (no commentary, preserve markers, etc.)
- Language register guidance (formal, technical, legal, etc.)

**User prompt** (`payload["prompt"]`) — dynamic per request:
- Language direction line: `"Translate from {src} to {tgt}:"`
- Source text (or merged segments with `<<<SEG_N>>>` markers for batch)
- Batch-specific instructions when using merged context (marker preservation rules)

- **Why**: Ollama caches system prompts in KV cache, so the same domain prompt across hundreds of segments is only encoded once. User prompt changes per-segment without invalidating the KV cache. Cleaner separation of concerns — domain knowledge lives in profiles, translation mechanics live in prompt builders.
- **Alternatives considered**: Prepend system prompt to user prompt (works but misses Ollama's KV optimization; harder to maintain; mixes concerns).

### Decision 3: Profile-internal prompt branching (no user-facing model param)
The frontend sends only `profile` (not `model`). The backend resolves the profile to get `model` and `system_prompt`. The prompt branching is then determined by the **resolved profile's model name**, not by a user-supplied parameter:
1. If `"translategemma"` in `profile.model` → use legacy translategemma prompt format, no `system` field, ignore `system_prompt`.
2. Else if `system_prompt` is non-empty → use two-tier architecture (system + user prompt).
3. Else → use generic prompt path.

The `POST /api/jobs` endpoint replaces `model: Optional[str] = Form(None)` with `profile: Optional[str] = Form(None)`. The old `model` parameter is removed entirely.
- **Why**: Eliminates the `model` + `profile` conflict. Users don't need to know which Ollama model a profile uses — that's an implementation detail. TranslateGemma compatibility is preserved at the code level for any profile that happens to specify a translategemma model, but no current profile does (all 7 use `qwen3.5:9b`).

### Decision 4: Domain-specific system prompts with terminology guidance
Each profile's system prompt follows a consistent structure:
1. **Role declaration** — "You are a professional translator specializing in {domain}."
2. **Terminology guidance** — Domain-specific terms, abbreviations, and conventions that must be preserved or correctly translated (e.g., MOSFET, FinFET, CMP for semiconductor; FMEA, SOP, ISO for manufacturing).
3. **Register and tone** — Formal/technical/legal as appropriate for the domain.
4. **Output rules** — "Output ONLY the translated text. No explanations, no markdown wrapping, no commentary. Preserve all formatting markers."
5. **Numerical/code preservation** — "Preserve all numbers, units, chemical formulas, model numbers, and code exactly as-is."

- **Why**: Qwen 3.5 is a general-purpose instruct model. Without domain terminology guidance, it may use casual synonyms instead of industry-standard terms. Explicit terminology lists in system prompts keep translations consistent and professional.
- **Example system prompts**:
  - **General**: Emphasizes faithful translation, tone preservation, and clean output.
  - **Semiconductor**: Lists IC design, packaging, testing terms; MOSFET/FinFET/SOI/TSV conventions; emphasizes preserving technical abbreviations untranslated.
  - **FAB**: Lists lithography/etching/deposition/CMP/yield/defect density terms; equipment names (ASML, TEL, LAM) preserved as-is.
  - **Manufacturing**: Lists QC/SOP/FMEA/Lean/Six Sigma/ISO terms; production line vocabulary.
  - **Government**: Formal register; administrative/bureaucratic terminology; legal citation format preservation.
  - **Financial**: Financial instrument terms; preserves numerical data exactly; regulatory terminology (Basel, IFRS, GAAP).
  - **Legal**: Precise legal terminology; clause structure preservation; no paraphrasing; contract/statute language conventions.

### Decision 5: `_build_payload()` helper to reduce duplication
Currently, 6+ locations in `ollama_client.py` build payloads independently. A `_build_payload(prompt)` helper centralizes system prompt injection.
- **Why**: Single place to add `system` field; prevents forgetting it in retry/chunked/batch paths.
- **Implementation**: `_build_payload(prompt)` returns `{"model": self.model, "prompt": prompt, "options": self._build_options()}` plus `"system": self.system_prompt` when set.

### Decision 6: Cache key includes profile_id via `cache_model_key` property
The translation cache currently keys on `(text, target_lang, src_lang, model)`. With profiles, the same model can produce different translations. We add a `cache_model_key` property to `OllamaClient` that returns `"{model}::{profile_id}"`.
- **Why**: Minimal change — only 3 lines in `translation_service.py` change from `client.model` to `client.cache_model_key`. No changes to `TranslationCache` class itself.
- **Alternatives considered**: Add `profile_id` as a separate cache column (requires DB migration, more invasive).

### Decision 7: Cache `clear()` compatibility with composite keys
The current `TranslationCache.clear(model=...)` uses exact match: `WHERE LOWER(model) = ?`. With composite keys like `"qwen3.5:9b::semiconductor"`, passing just `"qwen3.5:9b"` would miss profile-tagged entries. We update `clear()` to use a two-condition query: `WHERE LOWER(model) = ? OR LOWER(model) LIKE ?` with params `(model.lower(), f"{model.lower()}::%")`.
- **Why**: The `::` separator is the boundary between model name and profile suffix. Using `model = ? OR model LIKE model + '::%'` matches the exact model name (no-profile entries) plus all `::` suffixed variants, without risk of matching unrelated models that share a prefix (e.g., `clear("qwen3")` won't touch `"qwen3.5:9b"`).
- **Edge case**: `clear()` with no model argument already deletes everything — unaffected.
- **Alternatives considered**: Plain `LIKE model%` (too greedy — could match `qwen3.5` when clearing `qwen3`); separate `profile_id` column (requires DB migration).

### Decision 8: Progress logging includes profile context
The `[CONFIG]` log line emitted at job start is extended to include the profile name. The `[TR]` progress lines remain unchanged since they don't reference the model.
- **Format**: `[CONFIG] model=qwen3.5:9b, profile=semiconductor, PDF output_format=docx, layout_mode=overlay`
- **Why**: Operators and users need to see which profile is active in the job logs. The frontend already parses `[CONFIG]` for display but doesn't extract structured fields from it — adding `profile=` is purely informational.
- **No changes to frontend parsing**: The `[CONFIG]` line is displayed as-is in the log viewer. No new regex patterns needed.

### Decision 9: Frontend fetches profiles from API
Profiles are not hardcoded in frontend. `GET /api/profiles` returns the list, frontend renders dynamically.
- **Response format**: `GET /api/profiles` returns a **bare JSON array** `[{id, name, description}, ...]`, not a wrapper object. No `ProfilesResponse` wrapper — the endpoint uses `response_model=List[ProfileItem]` directly.
- **Why**: Single source of truth in backend. Adding a profile requires no frontend changes. Bare array is simpler for the frontend to consume (`const profiles = await res.json()`).
- **Fallback**: If `GET /api/profiles` fails, frontend shows a single "General" entry with `id="general"` so the user can still submit jobs.
- **UI placement**: Profile selector card is always visible in the right column, above the collapsible Advanced Settings. Uses existing `.radio-group` / `.radio-option` CSS patterns.

### Decision 10: Tune defaults for RTX 4060 8GB to run near VRAM limits
To improve long-document coherence while avoiding repeated model paging between VRAM and RAM, this change updates runtime defaults toward a higher-but-stable context budget on 8GB cards:
- `OLLAMA_NUM_CTX` default: `5120` (from 4096)
- `DEFAULT_READ_TIMEOUT_S` default: `360` (from 180)
- `MAX_PARAGRAPH_CHARS` default: `2400` (from 2000)
- `MAX_MERGE_SEGMENTS` default: `12` (from 10)

- **Why**: On RTX 4060 8GB, `5120` is a practical near-limit target for Qwen 3.5 9B in this pipeline, providing better cross-paragraph continuity than 4096 while usually avoiding RAM spill behavior that hurts throughput.
- **Batching impact**: With the existing formula, `DEFAULT_MAX_BATCH_CHARS` increases from `5144` (ctx 4096) to `6680` (ctx 5120), allowing larger merged context windows.
- **Fallback**: If a deployment shows instability or VRAM pressure, reduce `OLLAMA_NUM_CTX` to `4608` as first-line fallback.

### Decision 11: `translate_tool.sh` injects tuned env defaults, but never overrides user intent
The startup script sets runtime defaults only when variables are unset:
- `OLLAMA_NUM_CTX=5120`
- `OLLAMA_NUM_GPU=99`
- `TRANSLATE_CONNECT_TIMEOUT=15`
- `TRANSLATE_READ_TIMEOUT=360`

- **Why**: Keeps one-command startup aligned with the tuned profile while preserving explicit user overrides (`VAR=... ./translate_tool.sh start`).
- **No lock-in**: Users can still choose conservative or aggressive tuning per machine by setting env vars before startup.

### Decision 12: Auto-detect source language as default
With Qwen 3.5 (a general-purpose instruct model), the model can infer the source language from the text itself. The frontend adds an "Auto-detect (自動偵測)" option to the source language selector and makes it the new default.

**User prompt when auto-detect is active:**
- `"Translate to {tgt}:"` (omits "from {src}")
- The model infers the source language from the input text.

**User prompt when explicit source is selected:**
- `"Translate from {src} to {tgt}:"` (unchanged from current behavior)

- **Why**: TranslateGemma required an explicit source language because it's a seq2seq model with fixed language pairs. Qwen 3.5 can auto-detect, which simplifies the UX — users no longer need to know or specify the source language for most documents. The cache layer already handles `src_lang=None` by normalizing to `"auto"` (via `src_lang or "auto"` in `translation_service.py`), so `"auto"` is used directly as the cache key component — no further normalization is needed.
- **Alternatives considered**: langdetect pre-filter (adds dependency, accuracy concerns with short/mixed text — better as a separate proposal).

### Decision 13: Smart-skip via system prompt rule
All profile system prompts include two related rules:
1. "If the input text is already entirely in the target language, return it unchanged without modification."
2. "For short labels or column headers that already contain the target language translation alongside other languages (e.g., bilingual '品名 / Product Name'), return the original text unchanged."

The first rule handles mono-target-language segments. The second handles the common case of bilingual column headers in spreadsheets/tables where both the source and target language text are already present side by side.

- **Why**: Zero code cost — just two additional lines in each system prompt. Handles common cases: (a) text already fully in the target language, (b) bilingual table headers where re-translating would break the existing bilingual format. The model sees the target language and source text, so it can make this judgment per-segment.
- **Limitations**: Relies on the model's judgment, which may occasionally be wrong for mixed-language text. Acceptable trade-off since the alternative (langdetect) has the same accuracy issues and can't handle bilingual fields at all.

## Risks / Trade-offs
- **Risk**: Qwen 3.5 9B may produce verbose output (explanations, markdown wrapping) for some inputs.
  - **Mitigation**: System prompt explicitly forbids commentary. Existing post-processing and retry logic handles edge cases.
- **Risk**: Vietnamese translation quality untested with Qwen.
  - **Mitigation**: Qwen 2.5+ officially supports Vietnamese as a core language (29 languages, 18T training tokens). User should run A/B test with a small sample before full migration.
- **Risk**: Existing translategemma cache entries become orphaned after model change.
  - **Mitigation**: Cache naturally separates by model name. Old entries remain but won't be hit. No migration needed. User can clear cache if desired via `DELETE /api/cache?model=translategemma:12b`.
- **Risk**: Cache `clear(model=X)` might accidentally delete entries for models whose name is a prefix of another (e.g., `qwen3` matching `qwen3.5:9b`).
  - **Mitigation**: The query uses `model = ? OR model LIKE ?` with `model + '::%'` (not plain `model%`). The `::` separator ensures only exact model name and its profile-suffixed variants are matched. `clear("qwen3")` deletes `"qwen3"` and `"qwen3::foo"` but NOT `"qwen3.5:9b"` or `"qwen3:1b"`.
- **Risk**: System prompt tokens consume KV cache VRAM even though they are shared across requests.
  - **Mitigation**: System prompts are kept concise (~200-400 tokens each). At 5120 context, this is typically low overhead. Ollama caches system prompt KV across requests to the same model, so the cost is amortized.
- **Risk**: `OLLAMA_NUM_CTX=5120` may exceed stable VRAM envelope on some 8GB environments (driver fragmentation, additional GPU consumers).
  - **Mitigation**: Keep startup env override support; document `OLLAMA_NUM_CTX=4608` fallback; preserve chunking and retry paths for long inputs.

## Migration Plan
1. Deploy code changes (profiles, system prompt support, UI)
2. Ensure `qwen3.5:9b` is pulled in Ollama (`ollama pull qwen3.5:9b`)
3. Optionally clear old translategemma cache entries
4. No database migration required — cache key change is transparent
5. Verify `DELETE /api/cache?model=qwen3.5:9b` correctly clears all profile variants

## Open Questions
- None remaining (profile list, UI placement, and prompt architecture confirmed)
