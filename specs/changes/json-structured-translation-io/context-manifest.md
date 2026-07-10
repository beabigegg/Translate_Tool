# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- Table wire format — `app/backend/utils/table_serializer.py`
- Its five `serialize()`/`parse()` call sites — `xlsx_processor.py`, `pptx_processor.py`, `docx_processor.py`, `pdf_processor.py`, `services/translation_service.py`
- The two prompt builders that tell the model the wire format — `_build_table_translate_prompt` in `openai_compatible_client.py` and `ollama_client.py`
- Body wire format — `translate_merged_paragraphs` in `app/backend/utils/translation_helpers.py` → `client.translate_once`
- Contracts — `contracts/data/data-shape-contract.md` §Table Serialization Wire Format, `contracts/business/business-rules.md`

## Allowed Paths
- specs/changes/json-structured-translation-io/
- specs/context/project-map.md
- specs/context/contracts-index.md
- .cdd/code-map.yml
- app/backend/utils/table_serializer.py
- app/backend/utils/json_translation.py
- app/backend/utils/translation_helpers.py
- app/backend/clients/base_llm_client.py
- app/backend/clients/ollama_client.py
- app/backend/clients/openai_compatible_client.py
- app/backend/processors/xlsx_processor.py
- app/backend/processors/pptx_processor.py
- app/backend/processors/docx_processor.py
- app/backend/processors/pdf_processor.py
- app/backend/services/translation_service.py
- app/backend/services/translation_strategy.py
- app/backend/config.py
- contracts/data/data-shape-contract.md
- contracts/business/business-rules.md
- contracts/env/env-contract.md
- docs/adr/0006-table-markdown-serialization.md
- docs/adr/0016-context-out-of-band-system-channel.md
- docs/adr/0017-json-structured-translation-seam.md
- tests/test_table_serialization.py
- tests/test_table_context_translation.py
- tests/test_nontranslatable_segment_guard.py
- tests/test_pdf_layout_table_fixes.py
- tests/test_context_window_segments.py
- tests/test_openai_compatible_client.py
- tests/test_ollama_client_dynamic_strategy.py
- tests/test_llm_client_protocol.py
- tests/conftest.py

## Required Contracts
- contracts/data/data-shape-contract.md (§Table Serialization Wire Format — replace the pipe-grid with the JSON cell list, and ADD a consumers table; the section currently has none)
- contracts/business/business-rules.md (body envelope + schema validation, fallback discipline bound to BR-109 observability, BR-108 retire-or-keep decision; BR-107 and BR-68 stated as preserved)
- contracts/env/env-contract.md (conditional — only if a rollback flag is proven necessary)

## Required Tests
- tests/test_table_serialization.py (the wire-format unit tests)
- tests/test_table_context_translation.py (whole-table translation path)
- tests/test_nontranslatable_segment_guard.py (BR-107 / BR-108 — the meta-refusal tests live HERE; `tests/test_meta_refusal.py` does not exist)
- tests/test_pdf_layout_table_fixes.py (contains `_StubTableClient`, a known signature-mirroring double)
- tests/test_openai_compatible_client.py, tests/test_ollama_client_dynamic_strategy.py, tests/test_llm_client_protocol.py (client seam)
- new: JSON wire-format unit / contract / boundary / resilience tests

## Agent Work Packets

### change-classifier
- specs/changes/json-structured-translation-io/
- specs/context/project-map.md
- specs/context/contracts-index.md

### spec-architect
- specs/changes/json-structured-translation-io/
- .cdd/code-map.yml
- app/backend/utils/table_serializer.py
- app/backend/utils/translation_helpers.py
- app/backend/clients/openai_compatible_client.py
- app/backend/clients/ollama_client.py
- app/backend/services/translation_service.py
- app/backend/processors/xlsx_processor.py
- contracts/data/data-shape-contract.md
- contracts/business/business-rules.md
- docs/adr/0016-context-out-of-band-system-channel.md

### contract-reviewer
- specs/changes/json-structured-translation-io/
- contracts/data/data-shape-contract.md
- contracts/business/business-rules.md
- contracts/env/env-contract.md

### test-strategist
- specs/changes/json-structured-translation-io/
- .cdd/code-map.yml
- app/backend/utils/table_serializer.py
- app/backend/utils/translation_helpers.py
- tests/test_table_serialization.py
- tests/test_table_context_translation.py
- tests/test_nontranslatable_segment_guard.py
- tests/test_pdf_layout_table_fixes.py
- tests/test_context_window_segments.py
- tests/test_openai_compatible_client.py
- tests/test_ollama_client_dynamic_strategy.py
- tests/test_llm_client_protocol.py
- tests/conftest.py

### ci-cd-gatekeeper
- specs/changes/json-structured-translation-io/
- tests/test_table_serialization.py

### implementation-planner
- specs/changes/json-structured-translation-io/
- .cdd/code-map.yml
- app/backend/utils/table_serializer.py
- app/backend/utils/translation_helpers.py
- app/backend/clients/base_llm_client.py
- app/backend/clients/ollama_client.py
- app/backend/clients/openai_compatible_client.py
- app/backend/processors/xlsx_processor.py
- app/backend/processors/pptx_processor.py
- app/backend/processors/docx_processor.py
- app/backend/processors/pdf_processor.py
- app/backend/services/translation_service.py
- app/backend/services/translation_strategy.py
- contracts/data/data-shape-contract.md
- contracts/business/business-rules.md

### backend-engineer
- specs/changes/json-structured-translation-io/
- .cdd/code-map.yml
- app/backend/utils/table_serializer.py
- app/backend/utils/translation_helpers.py
- app/backend/clients/base_llm_client.py
- app/backend/clients/ollama_client.py
- app/backend/clients/openai_compatible_client.py
- app/backend/processors/xlsx_processor.py
- app/backend/processors/pptx_processor.py
- app/backend/processors/docx_processor.py
- app/backend/processors/pdf_processor.py
- app/backend/services/translation_service.py
- app/backend/config.py
- tests/test_table_serialization.py
- tests/test_table_context_translation.py
- tests/test_nontranslatable_segment_guard.py
- tests/test_pdf_layout_table_fixes.py
- tests/test_openai_compatible_client.py
- tests/test_ollama_client_dynamic_strategy.py
- tests/conftest.py

### e2e-resilience-engineer
- specs/changes/json-structured-translation-io/
- app/backend/utils/table_serializer.py
- app/backend/utils/json_translation.py
- app/backend/services/translation_service.py
- tests/test_json_translation_body.py
- tests/test_nontranslatable_segment_guard.py
- app/backend/utils/translation_helpers.py
- app/backend/processors/xlsx_processor.py
- tests/test_table_serialization.py
- tests/test_table_context_translation.py
- tests/conftest.py

### qa-reviewer
- specs/changes/json-structured-translation-io/
- contracts/data/data-shape-contract.md
- contracts/business/business-rules.md
- tests/test_table_serialization.py
- tests/test_table_context_translation.py

## Context Expansion Requests
- request-id: CER-001
  requested_paths:
    - tests/test_table_serialization.py
    - tests/test_table_context_translation.py
    - tests/test_pdf_layout_table_fixes.py
  reason: the classifier could not enumerate these from the truncated project-map tests/ listing and inferred a `tests/test_meta_refusal.py` that does not exist. Main Claude greped before writing this manifest; the real files are the three above, and the meta-refusal tests live in `tests/test_nontranslatable_segment_guard.py`.
  status: approved

- request-id: CER-002
  requested_paths:
    - .cdd/code-map.yml
  reason: to confirm the exact `serialize`/`parse` signatures and every downstream reader before the wire format changes, per the "no-shell agents can assert nonexistent seams" rule.
  status: approved

- request-id: CER-004
  requested_paths:
    - app/backend/utils/json_translation.py
    - tests/test_json_translation_body.py
  reason: e2e-resilience-engineer needed the module this change creates in order to write its resilience tests; it was absent from the manifest.
  status: approved
  approved-by: main-claude
  note: >-
    Granted. Reading the module this change creates is plainly in scope for the
    agent writing its resilience tests. The agent was right to file the CER rather
    than read it silently, and right to treat the module as a black box meanwhile.
