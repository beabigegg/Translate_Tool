---
artifact: project-map
generated-by: cdd-kit context-scan
schema-version: 1
root: Translate_Tool
visible-dirs: 57
visible-files: 190
omitted-dirs: 12
truncated-dirs: 0
inputs-digest: 58ec80699f498bf40074f81de6138b321f2d3ecc03137b33052a2dd7345722a2
---

# Project Map

Use this deterministic map to choose candidate context paths before reading files.

## Excluded Paths
- .claude
- .git
- node_modules
- dist
- build
- assets
- specs/archive
- specs/changes
- .cdd/.refresh-backup
- .cdd/migrate-backup
- .cdd/runtime
- .claude/worktrees

## Tree

```
Translate_Tool/
|-- .cdd/
|   |-- code-graph.index.json
|   |-- code-map.index.json
|   |-- code-map.yml
|   |-- conformance.json
|   |-- context-policy.json
|   |-- model-policy.json
|   \-- tier-policy.json
|-- .github/
|   \-- workflows/
|       \-- contract-driven-gates.yml
|-- .run/
|   \-- logs/
|       |-- backend.log
|       \-- frontend.log
|-- app/
|   |-- backend/
|   |   |-- api/
|   |   |   |-- __init__.py
|   |   |   |-- routes.py
|   |   |   \-- schemas.py
|   |   |-- clients/
|   |   |   |-- __init__.py
|   |   |   |-- base_llm_client.py
|   |   |   |-- ollama_client.py
|   |   |   \-- openai_compatible_client.py
|   |   |-- fonts/
|   |   |   |-- NotoSans-Regular.ttf
|   |   |   |-- NotoSansArabic-Regular.ttf
|   |   |   |-- NotoSansHebrew-Regular.ttf
|   |   |   |-- NotoSansJP-Regular.otf
|   |   |   |-- NotoSansJP-Variable.ttf
|   |   |   |-- NotoSansKR-Regular.otf
|   |   |   |-- NotoSansKR-Variable.ttf
|   |   |   |-- NotoSansSC-Regular.ttf
|   |   |   |-- NotoSansTC-Regular.ttf
|   |   |   \-- NotoSansThai-Regular.ttf
|   |   |-- models/
|   |   |   |-- __init__.py
|   |   |   |-- term.py
|   |   |   \-- translatable_document.py
|   |   |-- parsers/
|   |   |   |-- __init__.py
|   |   |   |-- base.py
|   |   |   |-- docx_parser.py
|   |   |   |-- layout_detector.py
|   |   |   |-- pdf_parser.py
|   |   |   \-- pptx_parser.py
|   |   |-- processors/
|   |   |   |-- __init__.py
|   |   |   |-- com_helpers.py
|   |   |   |-- docx_processor.py
|   |   |   |-- libreoffice_helpers.py
|   |   |   |-- orchestrator.py
|   |   |   |-- pdf_processor.py
|   |   |   |-- pptx_processor.py
|   |   |   \-- xlsx_processor.py
|   |   |-- renderers/
|   |   |   |-- __init__.py
|   |   |   |-- base.py
|   |   |   |-- bbox_reflow.py
|   |   |   |-- coordinate_renderer.py
|   |   |   |-- fitz_renderer.py
|   |   |   |-- inline_renderer.py
|   |   |   |-- pdf_generator.py
|   |   |   \-- text_region_renderer.py
|   |   |-- services/
|   |   |   |-- __init__.py
|   |   |   |-- context_prompts.py
|   |   |   |-- job_manager.py
|   |   |   |-- metrics.py
|   |   |   |-- model_router.py
|   |   |   |-- term_db.py
|   |   |   |-- term_extractor.py
|   |   |   |-- translation_cache.py
|   |   |   |-- translation_service.py
|   |   |   |-- translation_strategy.py
|   |   |   \-- wikidata_lookup.py
|   |   |-- utils/
|   |   |   |-- __init__.py
|   |   |   |-- bbox_utils.py
|   |   |   |-- exceptions.py
|   |   |   |-- font_utils.py
|   |   |   |-- logging_utils.py
|   |   |   |-- resource_utils.py
|   |   |   |-- text_utils.py
|   |   |   |-- translation_helpers.py
|   |   |   \-- translation_verification.py
|   |   |-- __init__.py
|   |   |-- config.py
|   |   |-- environment.yml
|   |   |-- main.py
|   |   |-- requirements.txt
|   |   \-- translation_profiles.py
|   |-- frontend/
|   |   |-- src/
|   |   |   |-- api/
|   |   |   |   \-- ... (max depth)
|   |   |   |-- components/
|   |   |   |   \-- ... (max depth)
|   |   |   |-- constants/
|   |   |   |   \-- ... (max depth)
|   |   |   |-- contexts/
|   |   |   |   \-- ... (max depth)
|   |   |   |-- hooks/
|   |   |   |   \-- ... (max depth)
|   |   |   |-- i18n/
|   |   |   |   \-- ... (max depth)
|   |   |   |-- pages/
|   |   |   |   \-- ... (max depth)
|   |   |   |-- styles/
|   |   |   |   \-- ... (max depth)
|   |   |   |-- App.jsx
|   |   |   \-- main.jsx
|   |   |-- index.html
|   |   |-- package-lock.json
|   |   |-- package.json
|   |   \-- vite.config.js
|   \-- __init__.py
|-- ci/
|   |-- gate-policy.md
|   \-- required-check-policy.md
|-- config/
|   |-- providers.yml
|   \-- providers.yml.example
|-- contracts/
|   |-- api/
|   |   |-- api-contract.md
|   |   |-- api-inventory.md
|   |   |-- error-format.md
|   |   \-- openapi.yml
|   |-- business/
|   |   \-- business-rules.md
|   |-- ci/
|   |   \-- ci-gate-contract.md
|   |-- css/
|   |   |-- css-contract.md
|   |   \-- design-tokens.md
|   |-- data/
|   |   \-- data-shape-contract.md
|   |-- env/
|   |   |-- .env.example.template
|   |   |-- env-contract.md
|   |   \-- env.schema.json
|   \-- CHANGELOG.md
|-- docs/
|   |-- adr/
|   |   |-- 0001-config-driven-provider-registry.md
|   |   |-- 0002-ir-elementtype-serialized-values.md
|   |   |-- 0003-layout-detector-runtime-and-failure-mode.md
|   |   \-- 0004-truncation-marker-on-ir.md
|   |-- improvement-plan.md
|   \-- p2-change-requests.md
|-- scripts/
|   |-- benchmark_full_factorial.py
|   |-- benchmark_realfile_pipeline.py
|   \-- run_full_factorial.sh
|-- specs/
|   |-- context/
|   |   |-- contracts-index.md
|   |   \-- project-map.md
|   \-- templates/
|       |-- archive.md
|       |-- change-classification.md
|       |-- change-request.md
|       |-- ci-gates.md
|       |-- context-manifest.md
|       |-- contracts.md
|       |-- current-behavior.md
|       |-- design.md
|       |-- implementation-plan.md
|       |-- monkey-test-report.md
|       |-- project-profile.md
|       |-- proposal.md
|       |-- qa-report.md
|       |-- regression-report.md
|       |-- spec.md
|       |-- stress-soak-report.md
|       |-- tasks.yml
|       |-- test-evidence.yml
|       |-- test-plan.md
|       \-- visual-review-report.md
|-- tests/
|   |-- contract/
|   |   |-- samples/
|   |   |   \-- .gitkeep
|   |   |-- README.md
|   |   \-- response-samples.example.json
|   |-- fixtures/
|   |   |-- golden/
|   |   |   |-- docx/
|   |   |   |   \-- ... (max depth)
|   |   |   |-- expansion/
|   |   |   |   \-- ... (max depth)
|   |   |   |-- pdf/
|   |   |   |   \-- ... (max depth)
|   |   |   |-- pptx/
|   |   |   |   \-- ... (max depth)
|   |   |   \-- README.md
|   |   \-- test.pdf
|   |-- templates/
|   |   |-- data-boundary/
|   |   |   \-- malformed-data.spec.md
|   |   |-- e2e/
|   |   |   \-- critical-journey.spec.md
|   |   |-- monkey/
|   |   |   \-- operation-sequence.spec.md
|   |   |-- resilience/
|   |   |   \-- api-failure.spec.md
|   |   |-- soak/
|   |   |   |-- k6-example.js
|   |   |   |-- locust-example.py
|   |   |   \-- soak-profile.md
|   |   \-- stress/
|   |       |-- artillery-example.yml
|   |       |-- k6-example.js
|   |       |-- load-profile.md
|   |       \-- locust-example.py
|   |-- __init__.py
|   |-- test_bbox_utils.py
|   |-- test_context_prompt_i18n.py
|   |-- test_coordinate_renderer.py
|   |-- test_docx_parser.py
|   |-- test_env_contract.py
|   |-- test_fewshot_glossary.py
|   |-- test_font_utils.py
|   |-- test_golden_regression.py
|   |-- test_hy_mt_quality_refinement.py
|   |-- test_inline_renderer.py
|   |-- test_ir_pipeline_decoupling.py
|   |-- test_layout_detector.py
|   |-- test_llm_client_protocol.py
|   |-- test_metrics_counters.py
|   |-- test_metrics_endpoint.py
|   |-- test_model_config_api.py
|   |-- test_model_router.py
|   |-- test_ollama_client_dynamic_strategy.py
|   |-- test_openai_compatible_client.py
|   |-- test_pdf_generator.py
|   |-- test_pdf_parser.py
|   |-- test_pptx_parser.py
|   |-- test_provider_fallback.py
|   |-- test_renderer_convergence.py
|   |-- test_sentence_mode_consistency.py
|   |-- test_table_border_protection.py
|   |-- test_term_api.py
|   |-- test_term_db.py
|   |-- test_term_extractor.py
|   |-- test_term_state_machine.py
|   |-- test_text_expansion_benchmark.py
|   |-- test_text_region_renderer.py
|   |-- test_translatable_document.py
|   |-- test_translation_profiles_scenarios.py
|   \-- test_translation_strategy.py
|-- .env
|-- .gitignore
|-- AGENTS.md
|-- CLAUDE.md
\-- translate_tool.sh
```
