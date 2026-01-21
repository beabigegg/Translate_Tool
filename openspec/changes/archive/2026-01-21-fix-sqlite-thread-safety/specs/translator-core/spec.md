## ADDED Requirements

### Requirement: Translation Cache Thread Safety
The translation cache SHALL be thread-safe and prevent deadlocks in multi-threaded environments.

#### Scenario: Concurrent cache reads
- **WHEN** multiple threads read from the cache simultaneously
- **THEN** each thread gets its own database connection
- **AND** reads complete without blocking each other
- **AND** connections are properly closed after use

#### Scenario: Concurrent cache writes
- **WHEN** multiple threads write to the cache simultaneously
- **THEN** writes are serialized via locking
- **AND** no data corruption occurs
- **AND** WAL mode enables concurrent reads during writes

#### Scenario: Connection cleanup
- **WHEN** a cache operation completes (success or failure)
- **THEN** the database connection is always closed
- **AND** no connection leaks occur over time
