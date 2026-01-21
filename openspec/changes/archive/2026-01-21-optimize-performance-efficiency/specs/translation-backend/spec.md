# Spec Delta: translation-backend

## ADDED Requirements

### Requirement: Job Lifecycle Management

The system SHALL automatically manage job records to prevent unbounded memory growth.

#### Scenario: Job count limit enforcement
- **GIVEN** the system has MAX_JOBS_IN_MEMORY configured (default: 100)
- **WHEN** a new job is created and total job count exceeds the limit
- **THEN** the oldest completed/failed/stopped jobs are removed
- **AND** their associated directories are deleted
- **AND** running jobs are never removed

#### Scenario: Job TTL expiration
- **GIVEN** the system has JOB_TTL_HOURS configured (default: 24)
- **WHEN** a job has been in completed/failed/stopped state for longer than TTL
- **THEN** the job record is eligible for cleanup
- **AND** its associated directories are deleted during the next cleanup cycle

#### Scenario: Periodic cleanup execution
- **GIVEN** the system has CLEANUP_INTERVAL_MINUTES configured (default: 30)
- **WHEN** the cleanup interval elapses
- **THEN** the system scans for expired jobs
- **AND** removes eligible job records and directories

#### Scenario: Startup orphan cleanup
- **WHEN** the JobManager initializes
- **THEN** it scans JOBS_DIR for directories without corresponding job records
- **AND** removes orphaned directories

---

### Requirement: Translation Cache Size Management

The system SHALL enforce size limits on the translation cache to prevent unbounded disk usage.

#### Scenario: Cache entry limit enforcement
- **GIVEN** the system has CACHE_MAX_ENTRIES configured (default: 50000)
- **WHEN** a new translation is cached and total entries exceed the limit
- **THEN** the least recently used entries are removed
- **AND** the removal is done in batches of CACHE_CLEANUP_BATCH (default: 5000)

#### Scenario: LRU tracking on cache access
- **WHEN** a cached translation is retrieved
- **THEN** the entry's last_used_at timestamp is updated
- **AND** the entry is less likely to be evicted

#### Scenario: Cache statistics retrieval
- **WHEN** cache statistics are requested
- **THEN** the system returns total entry count
- **AND** the system returns database file size

---

### Requirement: HTTP Connection Pooling

The system SHALL use connection pooling for Ollama API requests to improve efficiency.

#### Scenario: Connection reuse
- **GIVEN** an OllamaClient instance
- **WHEN** multiple API requests are made
- **THEN** HTTP connections are reused from a shared session pool
- **AND** TCP handshake overhead is avoided for subsequent requests

#### Scenario: Connection pool configuration
- **WHEN** the connection pool is initialized
- **THEN** it is configured with pool_connections=2 and pool_maxsize=5
- **AND** automatic retry with exponential backoff is enabled

#### Scenario: Session cleanup
- **WHEN** application shutdown is requested
- **THEN** the shared session is properly closed
- **AND** all pooled connections are released

---

### Requirement: SSE Stream Resource Management

The system SHALL properly manage Server-Sent Events streams to prevent resource leaks.

#### Scenario: Client disconnect detection
- **GIVEN** an active SSE log stream
- **WHEN** the client disconnects
- **THEN** the server-side generator stops within 5 seconds
- **AND** associated resources are released

#### Scenario: Idle timeout enforcement
- **GIVEN** SSE_IDLE_TIMEOUT_SECONDS configured (default: 60)
- **WHEN** no new log entries are generated for the timeout duration
- **THEN** the SSE stream is terminated
- **AND** the client receives stream end

#### Scenario: Job completion stream termination
- **WHEN** the job reaches completed/failed/stopped status
- **THEN** the SSE stream delivers remaining log entries
- **AND** the stream is terminated

---

### Requirement: Thread-Safe Job State Updates

The system SHALL ensure thread-safe updates to job state to prevent race conditions.

#### Scenario: Output archive state consistency
- **WHEN** a job completes and output is archived
- **THEN** the output_zip path is set within the job lock
- **AND** concurrent status checks see consistent output_ready state

#### Scenario: Concurrent status access
- **GIVEN** multiple concurrent requests for job status
- **WHEN** the job is transitioning between states
- **THEN** all requests receive consistent state information
- **AND** no partial state is observed

---

## MODIFIED Requirements

### Requirement: Translation Cache Schema

The translation cache database schema SHALL support LRU eviction tracking.

#### Scenario: Cache table structure
- **WHEN** the cache database is initialized
- **THEN** the translations table includes:
  - `id` INTEGER PRIMARY KEY AUTOINCREMENT
  - `src` TEXT NOT NULL (source language)
  - `tgt` TEXT NOT NULL (target language)
  - `text` TEXT NOT NULL (original text)
  - `result` TEXT NOT NULL (translated text)
  - `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  - `last_used_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
- **AND** a unique constraint exists on (src, tgt, text)
- **AND** an index exists on last_used_at for efficient LRU queries

#### Scenario: Backward compatibility
- **GIVEN** an existing cache database without timestamp columns
- **WHEN** the cache is opened
- **THEN** missing columns are added with default values
- **AND** existing data remains accessible

---

## Configuration Parameters

| Parameter | Default | Environment Variable | Description |
|-----------|---------|---------------------|-------------|
| MAX_JOBS_IN_MEMORY | 100 | MAX_JOBS_IN_MEMORY | Maximum job records in memory |
| JOB_TTL_HOURS | 24 | JOB_TTL_HOURS | Hours before completed jobs expire |
| CLEANUP_INTERVAL_MINUTES | 30 | CLEANUP_INTERVAL_MINUTES | Minutes between cleanup cycles |
| CACHE_MAX_ENTRIES | 50000 | CACHE_MAX_ENTRIES | Maximum cache entries |
| CACHE_CLEANUP_BATCH | 5000 | CACHE_CLEANUP_BATCH | Entries removed per cleanup |
| SSE_IDLE_TIMEOUT_SECONDS | 60 | SSE_IDLE_TIMEOUT_SECONDS | SSE idle timeout |
