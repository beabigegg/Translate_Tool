import React from 'react';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { render, screen } from '@testing-library/react';
import { SettingsProvider } from '../../contexts/SettingsContext.jsx';
import { TranslationProgress } from './TranslationProgress.jsx';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

beforeEach(() => {
  localStorage.clear();
});

function renderProgress(status) {
  return render(
    <SettingsProvider>
      <TranslationProgress status={status} />
    </SettingsProvider>
  );
}

// ---------------------------------------------------------------------------
// AC-3: StageDetailPanel renders current-segment content + stage badge label
// ---------------------------------------------------------------------------

test('test_renders_stage_detail_panel_with_current_segment_content', () => {
  renderProgress({
    status: 'running',
    overall_progress: 0.5,
    segments_done: 5,
    segments_total: 10,
    current_stage: 'critique',
    current_segment_source: 'Hello world source text',
    current_segment_draft: 'Bonjour draft text',
    current_segment_qe_score: 0.812,
    current_segment_adopted: true,
  });

  expect(screen.getByText('Hello world source text')).toBeTruthy();
  expect(screen.getByText('Bonjour draft text')).toBeTruthy();
  expect(screen.getByText(/0\.812/)).toBeTruthy();
});

test('test_stage_badge_label_matches_current_stage', () => {
  renderProgress({
    status: 'running',
    overall_progress: 0.5,
    segments_done: 5,
    segments_total: 10,
    current_stage: 'judge',
  });

  // zh-TW.js: 'stage.judge': '品質評審中'
  expect(screen.getByText('品質評審中')).toBeTruthy();
});

// ---------------------------------------------------------------------------
// AC-4: in-progress indicator survives segments_done == segments_total
// ---------------------------------------------------------------------------

test('test_shows_in_progress_indicator_when_segments_done_equals_total_but_stage_is_critique', () => {
  renderProgress({
    status: 'running', // isComplete is driven by status, not segment counts
    overall_progress: 0.99,
    segments_done: 10,
    segments_total: 10,
    current_stage: 'critique',
  });

  // zh-TW.js: 'stage.critique': '審校中' — visible even though 10/10 segments done.
  expect(screen.getByText('審校中')).toBeTruthy();
  expect(screen.getByText('10 / 10 段')).toBeTruthy();
});

// ---------------------------------------------------------------------------
// AC-7: resilience — absent/partial new fields never throw; panel renders nothing
// ---------------------------------------------------------------------------

test('test_renders_without_error_when_new_fields_absent_or_partial_mid_transition', () => {
  // No current_stage at all (older job / job just started) — StageDetailPanel
  // must render nothing, and the rest of the component must not throw.
  expect(() => renderProgress({
    status: 'running',
    overall_progress: 0.2,
    segments_done: 2,
    segments_total: 10,
  })).not.toThrow();

  // Partial mid-transition: current_stage set but source/draft not yet populated.
  expect(() => renderProgress({
    status: 'running',
    overall_progress: 0.3,
    segments_done: 3,
    segments_total: 10,
    current_stage: 'translate',
    current_segment_source: null,
    current_segment_draft: null,
  })).not.toThrow();
});

// ---------------------------------------------------------------------------
// AC-9: judge tier badge / attempt counter / substep label
// ---------------------------------------------------------------------------

test('test_renders_judge_tier_badge_attempt_counter_and_substep_label', () => {
  renderProgress({
    status: 'running',
    overall_progress: 0.9,
    segments_done: 9,
    segments_total: 10,
    current_stage: 'judge',
    current_segment_judge_tier: '中',
    current_segment_judge_attempt: 2,
    current_segment_judge_substep: 'retranslating',
  });

  expect(screen.getByText('中')).toBeTruthy();
  expect(screen.getByText(/2 \/ \d+/)).toBeTruthy();
  // zh-TW.js: 'stage.substep.retranslating': '重新翻譯中'
  expect(screen.getByText('重新翻譯中')).toBeTruthy();
});

test('test_renders_without_error_when_judge_fields_absent_non_judge_stage_or_older_job', () => {
  // Non-judge stage: judge-only fields must not render, must not throw.
  expect(() => renderProgress({
    status: 'running',
    overall_progress: 0.5,
    segments_done: 5,
    segments_total: 10,
    current_stage: 'critique',
    current_segment_judge_tier: null,
    current_segment_judge_attempt: null,
    current_segment_judge_substep: null,
  })).not.toThrow();

  // Older job: current_stage entirely absent from the payload (field didn't
  // exist yet) — must render without throwing (AC-7/AC-9 combined).
  expect(() => renderProgress({
    status: 'running',
    overall_progress: 0.1,
    segments_done: 1,
    segments_total: 10,
  })).not.toThrow();
});

// ---------------------------------------------------------------------------
// Static: no hardcoded hex colors (existing qualityTier hex must be migrated
// to CSS tokens; new StageBadge/JudgeTierBadge code must not introduce any)
// ---------------------------------------------------------------------------

test('test_no_hardcoded_hex_colors_in_source', () => {
  const source = fs.readFileSync(path.join(__dirname, 'TranslationProgress.jsx'), 'utf-8');
  const hexMatches = source.match(/#[0-9a-fA-F]{3,8}\b/g);
  expect(hexMatches).toBeNull();
});
