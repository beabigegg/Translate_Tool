## ADDED Requirements

### Requirement: Batch Translation Support
The system SHALL support batch translation to improve performance when processing multiple text segments.

#### Scenario: Batch multiple segments
- **WHEN** multiple unique text segments need translation
- **THEN** the system collects segments up to the configured batch size
- **AND** sends them as a single translation request
- **AND** distributes results back to the appropriate segments

#### Scenario: Configurable batch size
- **WHEN** user configures batch size in settings
- **THEN** the system respects the configured batch size
- **AND** defaults to a sensible value (e.g., 10) if not configured

#### Scenario: Single segment fallback
- **WHEN** only one segment needs translation
- **THEN** the system handles it without batching overhead
- **AND** maintains backward compatibility with existing behavior

#### Scenario: Batch error handling
- **WHEN** a batch translation request fails
- **THEN** the system falls back to individual segment translation
- **AND** logs the batch failure for debugging
