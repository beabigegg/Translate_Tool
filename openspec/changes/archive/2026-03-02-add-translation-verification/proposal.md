# Change: Add Translation Verification & Gap-Filling

## Why
When translations fail, error strings (e.g., `[Translation failed|zh-TW] 原文`) are stored in `tmap`, but all processors only check `(tgt, text) in tmap` (always True), causing error messages to be written into output files as if they were valid translations. Users receive documents with visible error markers instead of translated content.

## What Changes
- Add a post-translation verification step that scans translation results for known failure patterns
- Retry failed translations individually using `client.translate_once()`
- Integrate verification into all four processors (docx, xlsx, pptx, pdf)
- Add `VERIFY_MAX_RETRIES` configuration constant

## Impact
- Affected specs: `translator-core`
- Affected code: `config.py`, `docx_processor.py`, `xlsx_processor.py`, `pptx_processor.py`, `pdf_processor.py`
- New file: `app/backend/utils/translation_verification.py`

## Out of Scope
- Changing the batch translation pipeline itself
- Modifying the error string format
- Adding UI indicators for verification status
