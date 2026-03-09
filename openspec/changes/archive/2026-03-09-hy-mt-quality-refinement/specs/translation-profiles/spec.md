## MODIFIED Requirements

### Requirement: HY-MT Profiles Include Naturalness Guidance
All HY-MT-routed translation profiles SHALL include explicit guidance to prefer natural, idiomatic phrasing over literal word-for-word translation.

#### Scenario: Shared output rules include naturalness rule
- **GIVEN** any profile built with `_build_system_prompt()`
- **WHEN** the system prompt is constructed
- **THEN** the output rules block SHALL include a rule stating: prefer natural and idiomatic phrasing in the target language over literal or word-for-word translation

#### Scenario: technical_process register_tone includes naturalness
- **GIVEN** the `technical_process` profile (used for Vietnamese, Japanese, German routes)
- **WHEN** the system prompt is generated
- **THEN** the `register_tone` field SHALL instruct the model to use clear, natural phrasing readable by operators in the target language, not just a literal rendering of the Chinese source

#### Scenario: business_finance register_tone includes naturalness
- **GIVEN** the `business_finance` profile
- **WHEN** the system prompt is generated
- **THEN** the `register_tone` SHALL include guidance to use idiomatic business language of the target locale, not calque expressions

#### Scenario: marketing_pr register_tone includes naturalness
- **GIVEN** the `marketing_pr` profile
- **WHEN** the system prompt is generated
- **THEN** the `register_tone` SHALL emphasize localization-first: adapt idioms and expressions to target-market natural usage

### Requirement: HY-MT Translation Prompt Includes Naturalness Directive
`_build_translation_dedicated_prompt()` for non-Chinese directions SHALL include guidance to produce natural, idiomatic output.

#### Scenario: Non-Chinese direction prompt
- **GIVEN** target language is Vietnamese, Japanese, German, Korean (non-Chinese)
- **WHEN** `_build_translation_dedicated_prompt()` builds the user prompt
- **THEN** the prompt SHALL instruct the model to prefer natural phrasing over literal translation
- **AND** still instruct: output translation only, no explanation

#### Scenario: Chinese direction prompt unchanged
- **GIVEN** target language involves Chinese (Traditional or Simplified)
- **WHEN** `_build_translation_dedicated_prompt()` is called
- **THEN** the Chinese-language prompt SHALL remain unchanged (already effective for CJK routes)
