# ADR 0004: Truncation marker carried on the TranslatableDocument IR

## Status
proposed

## Context
p2-text-expansion replaces silent over-shrink/truncation with an ordered fit cascade
whose last resort is truncation. AC-5 requires every truncation to be machine-readable
by the QA safety net and human-review tooling, with no silent truncation. Two representations
were considered: (a) a render-time-only log/side-channel, and (b) an additive field on the IR
element. Truncation is decided by the renderer (a render-time outcome), yet it must be queryable
downstream and survive IR re-serialization, which is the IR's job per the data-shape contract.

## Decision
Record truncation as an additive optional field on `TranslatableElement`
(e.g. `render_truncated: bool`, default `False`), set by the converged renderer when the
cascade reaches its truncation step. It serializes through the existing `to_dict()` / `from_dict()`
surface. Old-format IR dicts lacking the key deserialize with the default, matching the existing
`reading_order` backward-compatibility rule. The field is a render annotation owned by the renderer
but persisted on the IR; it is not a structural `ElementType` and not a separate side-channel.

## Consequences
- `data-shape-contract.md` becomes an authoritative surface for this change and must document the
  additive field and its backward-compatibility behavior.
- QA/human-review tooling reads truncation state through the IR it already consumes; no new transport.
- The IR now carries a render-outcome field, mildly blurring the parse↔render decoupling; this is
  bounded to one optional flag and must not grow into general render-state storage on the IR.
- Reversing this later (moving the marker off the IR) would silently break any QA consumer that
  reads `render_truncated` from serialized IR — hence this ADR.
