# Change Request

## Original Request

Wire CONTEXT_WINDOW_SEGMENTS into LLM translation prompt: include adjacent segments as context window (item 0.6 of improvement plan).

CONTEXT_WINDOW_SEGMENTS=2, CONTEXT_MAX_CHARS=300, and MAX_MERGE_SEGMENTS=4 are defined in config.py (lines 104-105) but never used. Every segment translates in complete isolation with no adjacent context. The fix should pass up to CONTEXT_WINDOW_SEGMENTS adjacent segment texts as "Context (do not translate):" prefix in the LLM prompt, capped by CONTEXT_MAX_CHARS. CONTEXT_WINDOW_SEGMENTS=0 must disable context (backward compat). Unit test must verify prompt for segment N contains text from segment N-1 (non-tautological: mock at actual LLM call site, check specific adjacent text appears).

## Business / User Goal

## Non-goals

## Constraints

## Known Context

## Open Questions

## Requested Delivery Date / Priority
