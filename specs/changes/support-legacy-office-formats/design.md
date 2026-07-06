# Design: support-legacy-office-formats

## Summary
Legacy `.doc`/`.xls`/`.ppt` uploads are supported by converting them to their modern
counterparts (`.docx`/`.xlsx`/`.pptx`) via LibreOffice-headless subprocess *before* they
enter the existing extraction → layout-detection → translation → rendering → QE pipeline.
`.doc`/`.xls` conversion already exists in `orchestrator.py`/`libreoffice_helpers.py`; this
change adds the missing `.ppt` branch (`ppt_to_pptx`) mirroring the established pattern,
backfills test coverage for all three, and formalizes LibreOffice as a documented optional
binary dependency. Because LibreOffice conversion is inherently lossy for layout, the design
adds a user-facing disclosure — reusing the existing `warnings[]` job-status carrier — rather
than inventing new API surface or a special QE threshold. No native binary parser and no new
data schema are introduced.

## Affected Components
| component | file path(s) | nature of change |
|---|---|---|
| Conversion helper | `app/backend/processors/libreoffice_helpers.py` | add `ppt_to_pptx()` mirroring `doc_to_docx()`/`xls_to_xlsx()`; reuse `is_libreoffice_available()` |
| Orchestrator (main pipeline) | `app/backend/processors/orchestrator.py` (add `.ppt` branch beside `.pptx` at ~L766, mirror `.doc` L727-765) | route `.ppt` → temp `.pptx` → `translate_pptx()`; emit conversion warning; temp cleanup in `finally` |
| Orchestrator (Phase-0 extraction) | `app/backend/processors/orchestrator.py` (~L237, mirror `.xls` L243-255 / `.doc` L271-285) | add `.ppt` extraction branch with filename-stem fallback when LibreOffice absent |
| Supported extensions | `app/backend/config.py:245` | add `.ppt` to `SUPPORTED_EXTENSIONS` |
| Frontend upload surface | `app/frontend/src/constants/fileTypes.js`, `components/domain/FileDropZone.jsx` | add `.doc`/`.xls`/`.ppt` to `ACCEPTED_EXTENSIONS` + drop-zone copy |
| API contract | `contracts/api/api-contract.md` (+ re-export `openapi.yml`) | extend accepted-upload types; extend `warnings[]` note to cover legacy-conversion disclosure |
| Business rules | `contracts/business/business-rules.md` (BR-9 family) | new rule: legacy lossy-conversion disclosure + QE-boundary policy |
| Env contract | `contracts/env/env-contract.md`, `environment.yml`, README/docs | new "External Binary Dependencies" section documenting LibreOffice optional binary |
| QE service | `app/backend/services/quality_evaluator.py` | none (unchanged — see Decision 1) |

## Key Decisions
- **Disclosure via existing `warnings[]` field, not a new job field**: the job-status schema
  already carries `warnings: string[]` (api-contract L158) — an additive, backward-compatible
  degradation-notice channel populated today by the PDF fitz→ReportLab fallback and by
  output_mode degradation, emitted through the orchestrator's existing `warnings_callback`
  seam (L695-706, L816). Legacy conversion emits one entry per converted file
  ("`.ppt` file X converted from a legacy format via LibreOffice; layout fidelity may be lower
  than a native `.pptx`"). → rejected alternative: a new boolean `source_format_converted`
  field — duplicates what `warnings[]` already conveys, expands API/schema surface and OpenAPI
  export for no consumer benefit beyond a human-readable notice the frontend already renders.
- **No distinct QE threshold or QE reinterpretation for converted documents**: `quality_evaluator.py`
  is a stateless, reference-free scorer of `(src, mt)` translation pairs — it measures
  *translation adequacy*, not *layout fidelity*. Conversion loss is a layout/formatting axis
  orthogonal to what COMET scores; a QE score means exactly the same thing for a converted doc.
  Converted docs flow through the identical QE path unchanged. → rejected alternative: a separate
  QE threshold / "score is only advisory" reinterpretation for converted docs — conflates two
  independent quality axes and would mislead users into reading QE as a fidelity signal. Captured
  in ADR-0009 because a future engineer must not silently reverse this by adding a conversion QE penalty.
- **Silent reuse rejected**: doing nothing violates the user's explicit goal (揭露轉檔風險 / make
  lossy-conversion risk transparent). Since the `warnings[]` machinery already exists, disclosure
  is nearly free.
- **`.ppt` data-flow mirrors `.doc` exactly**: convert to a temp file, translate the temp file,
  clean up in `finally`. Failure semantics MUST match the existing pattern and invent nothing new:
  LibreOffice unavailable → log an actionable install message and `continue` (skip file, no crash,
  mirror L735-742); conversion raises → caught by the per-file `try/except` at L826-827 (`[ERROR]`
  log, proceed to next file). No new job status, no HTTP error, no failed-job transition.
- **env-contract needs a new section**: the contract today documents only env vars (L11-49); add an
  "External Binary Dependencies" subsection for LibreOffice — install (`apt install libreoffice-core`
  / `brew install --cask libreoffice`), detection via `is_libreoffice_available()`, degradation
  (legacy formats skipped-with-notice when absent; modern formats unaffected).

## Migration / Rollback
Purely additive: no schema migration, no data backfill, no breaking API change (`warnings[]` and the
new upload types are backward-compatible optional additions). "Rollback" means reverting the additive
surface: remove `.ppt` from `SUPPORTED_EXTENSIONS` (config.py) and from frontend `ACCEPTED_EXTENSIONS`,
which stops the UI from accepting the new type; the orchestrator `.ppt` branch and `ppt_to_pptx()` can
remain dormant harmlessly. The `.doc`/`.xls` paths already ship in production, so rollback of this change
does not touch them. If LibreOffice conversion proves unreliable in production, the fastest lever is the
extension whitelist (config + frontend) — no code deploy of the pipeline is required to stop accepting
legacy uploads. A per-family feature flag is not warranted at Tier 2 given the extension whitelist
already provides a clean off switch.

## Open Risks
- LibreOffice conversion fidelity varies by document complexity; disclosure mitigates but does not
  eliminate user surprise. Acceptable per the change's stated Non-goals.
- CI determinism when LibreOffice is absent on a runner (skip-with-marker vs required) is deferred to
  ci-cd-gatekeeper per classification; not resolved here.
- `.ppt` COM fallback parity: the `.doc` branch has a `win32com` fallback (L732-734); whether `.ppt`
  gets an equivalent `powerpoint_convert` COM path is left to implementation-planner/backend-engineer
  (LibreOffice + graceful skip is the minimum bar).
