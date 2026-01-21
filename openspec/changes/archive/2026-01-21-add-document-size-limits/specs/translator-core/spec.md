## ADDED Requirements

### Requirement: Document Size Limits
The system SHALL enforce document size limits to prevent memory exhaustion.

#### Scenario: Segment count limit exceeded
- **WHEN** a document contains more than MAX_SEGMENTS segments (default: 10,000)
- **THEN** the system raises an error before processing
- **AND** displays a user-friendly message indicating the limit and actual count

#### Scenario: Character count limit exceeded
- **WHEN** a document's total text exceeds MAX_TEXT_LENGTH characters (default: 100,000)
- **THEN** the system raises an error before processing
- **AND** displays a user-friendly message indicating the limit and actual count

#### Scenario: Document within limits
- **WHEN** a document is within both segment and character limits
- **THEN** processing proceeds normally
- **AND** no additional overhead is introduced

#### Scenario: Configurable limits
- **WHEN** user has configured custom limit values
- **THEN** the system uses the configured values instead of defaults
