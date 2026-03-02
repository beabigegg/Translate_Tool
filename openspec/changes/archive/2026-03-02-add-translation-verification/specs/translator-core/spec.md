## ADDED Requirements

### Requirement: Translation Result Verification
The system SHALL verify translation results after batch translation and retry failed segments individually.

#### Scenario: Detect failed translations in tmap
- **WHEN** batch translation completes with failures
- **THEN** the system SHALL scan all entries in the translation map for known failure patterns
- **AND** the system SHALL identify entries matching patterns such as `[Translation failed|`, `[翻譯失敗]`, `[No translation|`, `[Translation missing`, `[Extended retry failed`, `[Chunked translation failed`, `[Chunk translation failed]`, `[Missing translation result]`

#### Scenario: Retry failed translations
- **WHEN** failed translation entries are detected
- **THEN** the system SHALL retry each failed entry up to VERIFY_MAX_RETRIES times using `client.translate_once()`
- **AND** the system SHALL update the translation map in-place with successful retries
- **AND** the system SHALL apply OpenCC Traditional Chinese conversion when the target language requires it

#### Scenario: Stop flag respected during verification
- **WHEN** the stop flag is set during verification
- **THEN** the system SHALL abort the verification loop
- **AND** the system SHALL log the interruption

#### Scenario: Verification logging
- **WHEN** verification runs
- **THEN** the system SHALL log the number of gaps found, filled, and remaining with `[VERIFY]` prefix

#### Scenario: PDF dict-based verification
- **WHEN** PDF translation produces a `Dict[str, str]` result
- **THEN** the system SHALL verify and retry failed entries in the dict format
- **AND** the system SHALL apply the same failure detection and retry logic as tmap verification
