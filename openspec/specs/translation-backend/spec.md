# Translation Backend Specification

## Purpose
Defines the translation backend configuration and behavior, including support for local TranslateGemma model via Ollama service, health checks, and timeout settings.

## Requirements

### Requirement: TranslateGemma Local Translation Backend
The system SHALL support TranslateGemma:12b as the primary local translation backend via Ollama service.

#### Scenario: Successful translation with TranslateGemma
- **GIVEN** Ollama service is running with TranslateGemma:12b model loaded
- **WHEN** user submits text for translation with target language "English"
- **THEN** the system SHALL send a properly formatted prompt to Ollama API
- **AND** return the translated text without additional commentary

#### Scenario: TranslateGemma prompt format
- **GIVEN** source text "你好世界" with source language "Auto" and target language "English"
- **WHEN** the translation request is processed
- **THEN** the system SHALL construct a prompt following TranslateGemma's official format:
  - Include professional translator role description
  - Specify source and target languages with ISO codes
  - Request translation-only output without explanations
  - Append the source text at the end

#### Scenario: Language code mapping
- **GIVEN** a target language name from the GUI (e.g., "Traditional Chinese")
- **WHEN** constructing the TranslateGemma prompt
- **THEN** the system SHALL map to the correct ISO language code (e.g., "zh-TW")

### Requirement: Ollama Health Check Enhancement
The system SHALL verify Ollama service availability and model readiness before translation.

#### Scenario: Ollama service healthy
- **GIVEN** Ollama service is running on localhost:11434
- **WHEN** health check is performed
- **THEN** the system SHALL confirm service availability
- **AND** list available models including translategemma:12b

#### Scenario: Ollama service unavailable
- **GIVEN** Ollama service is not running
- **WHEN** health check is performed
- **THEN** the system SHALL display an error message indicating Ollama is not accessible
- **AND** suggest user to start Ollama service

### Requirement: Extended Timeout for Local Inference
The system SHALL use extended timeout settings for local model inference.

#### Scenario: Long text translation timeout
- **GIVEN** a document with paragraphs exceeding 500 characters
- **WHEN** translating via TranslateGemma locally
- **THEN** the system SHALL allow up to 180 seconds for API response
- **AND** not timeout prematurely during model inference

### Requirement: Default Model Selection
The system SHALL default to TranslateGemma:12b model when available.

#### Scenario: Application startup with Ollama available
- **GIVEN** Ollama service is running
- **WHEN** the application starts
- **THEN** the model dropdown SHALL default to "translategemma:12b" if available

#### Scenario: Application startup without Ollama
- **GIVEN** Ollama service is not running
- **WHEN** the application starts
- **THEN** the system SHALL display a warning that Ollama is not available
- **AND** suggest user to start Ollama service
