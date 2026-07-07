---
contract: design-tokens
summary: Canonical design token inventory for colors, spacing, typography, and layering.
owner: design-system
surface: ui
---

# Design Tokens

## Colors

| token | value | usage |
|---|---|---|
| `--color-quality-high` | (green family — implementation defines exact shade) | JudgeBadge: score 高 |
| `--color-quality-mid` | (yellow/amber family — implementation defines exact shade) | JudgeBadge: score 中 |
| `--color-quality-low` | (red family — implementation defines exact shade) | JudgeBadge: score 低 |
| `--color-stage-translate` | (implementation defines exact shade) | StageBadge: current_stage = translate |
| `--color-stage-critique` | (implementation defines exact shade) | StageBadge: current_stage = critique |
| `--color-stage-qe` | (implementation defines exact shade) | StageBadge: current_stage = qe |
| `--color-stage-adopt` | (implementation defines exact shade) | StageBadge: current_stage = adopt |
| `--color-stage-judge` | (implementation defines exact shade) | StageBadge: current_stage = judge |
| `--color-stage-judge-high` | reuses/parallels `--color-quality-high` (green family) | StageBadge judge-tier sub-variant: current_segment_judge_tier = 高 |
| `--color-stage-judge-mid` | reuses/parallels `--color-quality-mid` (yellow/amber family) | StageBadge judge-tier sub-variant: current_segment_judge_tier = 中 |
| `--color-stage-judge-low` | reuses/parallels `--color-quality-low` (red family) | StageBadge judge-tier sub-variant: current_segment_judge_tier = 低 |
| `--color-quality-tier-excellent` | (green family — same family as `--color-quality-high`) | completion-panel `quality_score_avg` tier badge: score ≥ 0.85 (「高品質」) — migrated from the previously hardcoded `qualityTier()` hex in `TranslationProgress.jsx` |
| `--color-quality-tier-good` | (lime family) | completion-panel tier badge: 0.70 ≤ score < 0.85 (「良好」) — migrated from `qualityTier()` |
| `--color-quality-tier-acceptable` | (amber family — same family as `--color-quality-mid`) | completion-panel tier badge: 0.55 ≤ score < 0.70 (「可接受」) — migrated from `qualityTier()` |
| `--color-quality-tier-needs-review` | (red family — same family as `--color-quality-low`) | completion-panel tier badge: score < 0.55 (「需審校」) — migrated from `qualityTier()` |

## Spacing

## Typography

## Radius / Shadow

## Z-index

## Token Addition Policy
