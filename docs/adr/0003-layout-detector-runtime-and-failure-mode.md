# ADR 0003: Layout detector runtime default and inference-failure mode

## Status
proposed

## Context
`p2-layout-detection` adds `app/backend/parsers/layout_detector.py`, which runs the local Docling heron-101 ONNX model (Apache-2.0, `docling-project/docling-layout-heron-onnx`) per PDF page to detect typed regions and assign reading order, replacing the `round(y0,10pt)` bucket heuristic in `pdf_parser.py`. Two decisions are load-bearing for deployment and operability and become expensive to reverse once golden fixtures and Docker bundling exist:

1. Whether the declared `onnxruntime` dependency targets CPU or GPU. This sets the trust/portability boundary for every image (CI, air-gapped, developer) and contends with the local Ollama GPU.
2. What happens when inference fails (model absent, ONNX load error, OOM, corrupt page). The parse path is the sole route to a translated document, so this choice governs whether a layout-quality regression can escalate into total job failure.

The parse pipeline already establishes a fail-soft contract: `pdf_processor.py` falls back PyMuPDF→PyPDF2 on any parser exception.

## Decision
1. **Runtime: CPU-only by default.** Declare CPU `onnxruntime` as the dependency. GPU is opt-in: an operator installs `onnxruntime-gpu` out-of-band and the detector auto-selects the CUDA execution provider when available, otherwise `CPUExecutionProvider`. No `ultralytics` dependency (AGPL risk).
2. **Failure mode: fail-soft.** On any inference failure the detector falls back per-affected-page to the legacy `round(y0,10pt)` reading-order heuristic and the job continues; the failure is logged at WARNING (page number + reason) with no page image or content in the log. A fully-absent model is surfaced once as a startup WARNING. The whole feature is gated by `LAYOUT_DETECTOR_ENABLED` for full disable.
3. **Privacy boundary:** the rasterised page image is created, consumed, and discarded inside the detector module; weights may be fetched from HuggingFace, but page data never leaves the process. The module imports no network client.

## Consequences
- Images stay portable and CI/offline-reproducible; GPU boxes benefit without a code or dependency change. A team wanting GPU-by-default must change the dependency manifest deliberately, not silently.
- A missing/optional model or transient OOM degrades reading-order quality on the affected page only, never loses the job — consistent with the existing parser fallback contract.
- The reading-order quality target (>95% multi-column) is gated by golden dual-run, independent of these decisions.
- Reversing to GPU-default or fail-hard later would regress portability or job durability; future engineers must treat both as deliberate, contract-backed choices (env contract + business-rules BR for the degradation rule), not defaults to flip.
- If model-availability needs to be observable, that is a separate change adding a health surface (and an api-contract update); it is intentionally out of scope here.
