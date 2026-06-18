# ADR 0002: IR ElementType serialized values and additive serialization envelope

## Status
proposed

## Context
`p2-ir-document-model` matures `TranslatableDocument` into the canonical parse→translate→render IR. Two serialization choices are load-bearing for the whole P2 layout track and, once golden-sample fixtures are committed, become expensive to reverse:

1. The four new region-level `ElementType` members (`TABLE`, `FIGURE`, `FORMULA`, `LIST`). The change-request names them in uppercase, but the eight existing members all serialize to lowercase strings (`text`, `title`, `table_cell`, …). The wire (serialized) value is what gets frozen into committed fixtures and into any persisted/job-scoped IR.
2. Whether the serialized envelope carries an explicit `schema_version` key to distinguish old-format from new-format documents.

Downstream changes (`p2-layout-detection`, `p2-renderer-convergence`) and the golden-sample regression gate depend on these being stable and unambiguous.

## Decision
1. Python enum member names are uppercase (`ElementType.TABLE`); their serialized string values are lowercase (`"table"`, `"figure"`, `"formula"`, `"list"`), matching the existing convention. All eight pre-existing values keep their current strings unchanged.
2. No `schema_version` key is added. Format detection is structural: a serialized `TranslatableElement` lacking the `reading_order` key is "old format" and deserializes with `reading_order=None`. The schema change is purely additive, so no version-gated branch is needed.
3. `from_dict` continues to raise `ValueError` on a genuinely unknown `element_type`; the new values are valid because they are added to the enum, not because errors are swallowed.

## Consequences
- Serialized IR stays internally consistent (all-lowercase element-type values); case-sensitive consumers and the golden diff are not split across two conventions.
- Old-format documents (no `reading_order`) remain deserializable forever without a migration; rollback to pre-change code is safe because that code reads only known keys and ignores the added one.
- The decision is hard to reverse after golden fixtures and any persisted IR exist: changing wire values later would invalidate every committed fixture and break stored documents. Future engineers must not silently switch to uppercase wire values or rename existing ones.
- A real breaking shape change in the future should introduce `schema_version` at that point (per the data contract's deprecate-2-minors policy), not retrofit it now.
