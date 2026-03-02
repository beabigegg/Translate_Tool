## 1. Implementation
- [ ] 1.1 Add `VERIFY_MAX_RETRIES = 2` to `app/backend/config.py`
- [ ] 1.2 Create `app/backend/utils/translation_verification.py` with failure detection and retry logic
- [ ] 1.3 Integrate `verify_and_fill_tmap()` into `docx_processor.py`
- [ ] 1.4 Integrate `verify_and_fill_tmap()` into `xlsx_processor.py`
- [ ] 1.5 Integrate `verify_and_fill_tmap()` into `pptx_processor.py`
- [ ] 1.6 Integrate `verify_and_fill_dict()` into `pdf_processor.py` (3 locations)

## 2. Validation
- [ ] 2.1 Verify module imports correctly
- [ ] 2.2 Verify `is_failed_translation()` covers all known error patterns
