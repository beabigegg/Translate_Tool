---
contract: api-error-format
summary: Standard error payload shape, safety rules, and reusable error code table.
owner: application-team
surface: api
---

# API Error Format

## Standard Error Shape

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "User-facing message",
    "details": "development-only or structured diagnostic data"
  }
}
```

Adapt the shape to each repo, but keep error code, user message, and safe diagnostic policy explicit.

## Error Codes
| code | status | user-facing message | retryable | owner |
|---|---:|---|---:|---|
