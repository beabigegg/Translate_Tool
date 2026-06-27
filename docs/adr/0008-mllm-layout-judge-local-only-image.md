# ADR 0008: MLLM layout-judge images stay local and in-memory

## Status
proposed

## Context
Task 4.2 of quality-metrics-gating adds an MLLM-as-judge layout score (1-5) for
PDF pages, reusing the existing local Gemma judge in `quality_judge.py`. Scoring
layout requires sending a rasterised page image to a multimodal model. This is a
new data flow: until now, rasterised PDF page images were created, consumed, and
discarded entirely within `layout_detector.py` and were never serialised,
persisted, logged, or sent over any socket (BR-32, local-inference-privacy). The
new judge path must send the page image to a model, which crosses that boundary.

The translation fallback chain (`model_router`) can route to cloud providers
(PANJIT, DeepSeek). The judge, by design D4, never uses `model_router` — it
always calls the configured local `JUDGE_MODEL` directly via `OllamaClient`.

## Decision
The MLLM layout judge receives the page as an **in-memory PIL image**, never a
file path, and sends it **only** to the local Ollama Gemma model. The image is
never written to disk, never logged, and never passed to `model_router` or any
cloud provider. `quality_judge.judge_layout()` accepts the image object; the PDF
processor owns rasterisation and is the sole caller. `JUDGE_ENABLED` remains
`false` by default, so the path is opt-in.

## Consequences
- BR-32's prohibitions on persistence and logging of page images are preserved;
  its "never sent over any socket" clause is narrowed for this opt-in path to
  "never sent to a non-local socket" — the image may reach the localhost Ollama
  endpoint only.
- A future engineer must not route layout-judge images through `model_router`
  or any cloud provider; doing so would exfiltrate document page images and
  silently reverse this decision. Any such change must supersede this ADR.
- Passing an in-memory image (not a path) keeps `quality_judge.py` decoupled
  from PDF storage internals and avoids a temp-file disk write.
