---
artifact: project-map
generated-by: cdd-kit context-scan
schema-version: 1
root: Translate_Tool
visible-dirs: 59
visible-files: 245
omitted-dirs: 12
truncated-dirs: 1
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
|   |   |   |-- ocr_backend.py
|   |   |   |-- pdf_parser.py
|   |   |   |-- pptx_parser.py
|   |   |   \-- table_recognizer.py
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
|   |   |   |-- doc_chunker.py
|   |   |   |-- job_manager.py
|   |   |   |-- layout_qa.py
|   |   |   |-- metrics.py
|   |   |   |-- model_router.py
|   |   |   |-- quality_evaluator.py
|   |   |   |-- quality_judge.py
|   |   |   |-- term_audit.py
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
|   |   |   |-- json_translation.py
|   |   |   |-- length_guard.py
|   |   |   |-- logging_utils.py
|   |   |   |-- resource_utils.py
|   |   |   |-- table_serializer.py
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
|   |   |   |-- main.jsx
|   |   |   \-- test-setup.js
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
|   |   |-- openapi.json
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
|   |   |-- 0004-truncation-marker-on-ir.md
|   |   |-- 0005-judge-rerender-apply.md
|   |   |-- 0006-table-markdown-serialization.md
|   |   |-- 0007-bilingual-docx-dual-column.md
|   |   |-- 0008-mllm-layout-judge-local-only-image.md
|   |   |-- 0009-legacy-conversion-disclosure-and-qe-boundary.md
|   |   |-- 0010-progress-detail-poll-piggyback.md
|   |   |-- 0011-cloud-llm-total-timeout-and-cancellable-post.md
|   |   |-- 0012-shared-fit-cascade-all-pdf-paths.md
|   |   |-- 0013-bounded-local-table-row-growth-prepass.md
|   |   |-- 0014-retire-phantom-br-and-inert-env-var.md
|   |   |-- 0015-layout-qa-metric-core-in-runtime.md
|   |   |-- 0016-context-out-of-band-system-channel.md
|   |   |-- 0017-json-structured-translation-seam.md
|   |   |-- 0018-nested-table-frame-routing.md
|   |   |-- 0019-native-header-footer-com-shape-boundary.md
|   |   |-- 0020-truncation-length-guard.md
|   |   \-- 0021-reasoning-suppression-harmony-system-directive.md
|   |-- TEST_DOC/
|   |   |-- CS2408-0021 信和達(歐朗) P6SMBJ18CA  本體破损 -onepage.pdf
|   |   |-- EN-P-QC1102-D7 量测系统分析(MSA)程序.docx
|   |   \-- W-RM0901-G6 机器设备保养及维护管理准则.docx
|   \-- improvement-plan.md
|-- scripts/
|   |-- benchmark_full_factorial.py
|   |-- benchmark_realfile_pipeline.py
|   |-- e2e_smoke.py
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
|   |   |   |-- .gitkeep
|   |   |   \-- job_quality_available.json
|   |   |-- README.md
|   |   |-- response-samples.example.json
|   |   |-- response-samples.json
|   |   \-- test_legacy_conversion_disclosure.py
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
|   |   |   |-- generate_simple_test_pdf.py
|   |   |   |-- README.md
|   |   |   \-- simple_test.pdf
|   |   |-- minimal_phase0.docx
|   |   |-- test_multiline.pdf
|   |   \-- test.pdf
|   |-- metrics/
|   |   |-- __init__.py
|   |   |-- biou.py
|   |   |-- residual_text.py
|   |   \-- truncation_rate.py
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
|   |-- conftest.py
|   |-- test_bbox_utils.py
|   |-- test_cloud_total_timeout.py
|   |-- test_context_prefix_bleed.py
|   |-- test_context_prompt_i18n.py
|   |-- test_context_window_segments.py
|   |-- test_coordinate_renderer.py
|   |-- test_critique_gate.py
|   |-- test_critique_loop_batching.py
|   |-- test_dead_references.py
|   |-- test_doc_chunker.py
|   |-- test_docx_body_textbox_dedup.py
|   |-- test_docx_header_footer.py
|   |-- test_docx_nested_tables.py
|   |-- test_docx_parser.py
|   |-- test_env_contract.py
|   |-- test_eta_multi_phase_heuristic.py
|   |-- test_fewshot_glossary.py
|   |-- test_font_utils.py
|   |-- test_glossary_enforcement.py
|   |-- test_golden_regression.py
|   |-- test_inline_renderer.py
|   |-- test_ir_pipeline_decoupling.py
|   |-- test_job_manager_current_segment.py
|   |-- test_job_record_judge.py
|   |-- test_jobstatus_download_url.py
|   |-- test_jobstatus_stage_detail.py
|   |-- test_json_translation_body.py
|   |-- test_json_translation_prompt.py
|   |-- test_judge_api.py
|   |-- test_judge_apply.py
|   |-- test_layout_detector.py
|   |-- test_layout_metrics.py
|   |-- test_layout_qa.py
|   |-- test_length_guard.py
|   |-- test_libreoffice_helpers.py
|   |-- test_llm_client_protocol.py
|   |-- test_metrics_counters.py
|   |-- test_metrics_endpoint.py
|   |-- test_model_config_api.py
|   |-- test_model_router.py
|   |-- test_nontranslatable_segment_guard.py
|   |-- test_ollama_client_dynamic_strategy.py
|   |-- test_openai_compatible_client.py
|   |-- test_orchestrator_context_detection.py
|   \-- ... (40 more entries truncated; cap=50)
|-- .env
|-- .gitignore
|-- AGENTS.md
|-- CLAUDE.md
|-- package-lock.json
|-- package.json
\-- translate_tool.sh
```
