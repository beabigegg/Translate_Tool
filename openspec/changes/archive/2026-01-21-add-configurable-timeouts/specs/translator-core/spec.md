## ADDED Requirements

### Requirement: Configurable Timeout Settings
The system SHALL allow users to configure timeout values for API calls.

#### Scenario: Default timeout values
- **WHEN** no timeout configuration is provided
- **THEN** the system uses sensible default values
- **AND** connect timeout defaults to 10 seconds
- **AND** read timeout defaults to 180 seconds for local models

#### Scenario: Configuration file timeout
- **WHEN** timeout values are specified in configuration file
- **THEN** the system uses the configured values
- **AND** invalid values are rejected with clear error messages

#### Scenario: Environment variable timeout
- **WHEN** timeout values are specified via environment variables
- **THEN** environment variables take precedence over config file
- **AND** the system reads TRANSLATE_CONNECT_TIMEOUT and TRANSLATE_READ_TIMEOUT

#### Scenario: Runtime timeout adjustment
- **WHEN** user needs longer timeouts for slow models
- **THEN** the timeout can be adjusted without code changes
- **AND** changes take effect on next API call
