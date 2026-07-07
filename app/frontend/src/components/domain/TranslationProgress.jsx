import React from 'react';
import { useTranslation } from '../../i18n/index.js';
import { JUDGE_MAX_ITERATIONS_DISPLAY } from '../../constants/defaults.js';

// Completion-panel quality tier (quality_score_avg, continuous 0-1 COMET score).
// Colors via CSS tokens only (translation-progress-detail-ui migration — no hardcoded hex).
function qualityTier(score) {
  if (score >= 0.85) return { label: '高品質', colorVar: '--color-quality-tier-excellent' };
  if (score >= 0.70) return { label: '良好', colorVar: '--color-quality-tier-good' };
  if (score >= 0.55) return { label: '可接受', colorVar: '--color-quality-tier-acceptable' };
  return { label: '需審校', colorVar: '--color-quality-tier-needs-review' };
}

// current_stage -> CSS token (translation-progress-detail-ui, css-contract.md StageBadge row)
const STAGE_COLOR_VARS = {
  translate: '--color-stage-translate',
  critique: '--color-stage-critique',
  qe: '--color-stage-qe',
  adopt: '--color-stage-adopt',
  judge: '--color-stage-judge',
};

// current_segment_judge_tier -> CSS token (reuses/parallels the migrated qualityTier tokens)
const JUDGE_TIER_COLOR_VARS = {
  '高': '--color-stage-judge-high',
  '中': '--color-stage-judge-mid',
  '低': '--color-stage-judge-low',
};

function StageBadge({ stage, label }) {
  if (!stage) return null;
  const colorVar = STAGE_COLOR_VARS[stage] || '--text-muted';
  return (
    <span
      className="stage-badge"
      style={{
        display: 'inline-block',
        padding: 'var(--space-1) var(--space-3)',
        borderRadius: 'var(--radius-full)',
        fontSize: 'var(--text-sm)',
        fontWeight: 700,
        color: 'var(--text-inverse)',
        background: `var(${colorVar})`,
      }}
    >
      {label}
    </span>
  );
}

function JudgeTierBadge({ tier }) {
  if (!tier) return null;
  const colorVar = JUDGE_TIER_COLOR_VARS[tier] || '--text-muted';
  return (
    <span
      className="judge-tier-badge"
      style={{
        display: 'inline-block',
        padding: 'var(--space-1) var(--space-2)',
        borderRadius: 'var(--radius-full)',
        fontSize: 'var(--text-xs)',
        fontWeight: 700,
        color: 'var(--text-inverse)',
        background: `var(${colorVar})`,
      }}
    >
      {tier}
    </span>
  );
}

/**
 * StageDetailPanel — conditionally-rendered current-segment detail
 * (translation-progress-detail-ui, css-contract.md StageDetailPanel row).
 * Renders NOTHING (clean absence) when current_stage is absent/null — the job
 * just started, critique+QE+judge are all inactive, or the poll caught a
 * mid-transition moment. Every individual field is independently null-tolerant.
 */
function StageDetailPanel({ status, t }) {
  const current_stage = status?.current_stage;
  if (!current_stage) return null;

  const current_segment_source = status?.current_segment_source;
  const current_segment_draft = status?.current_segment_draft;
  const current_segment_qe_score = status?.current_segment_qe_score;
  const current_segment_adopted = status?.current_segment_adopted;
  const current_segment_judge_tier = status?.current_segment_judge_tier;
  const current_segment_judge_attempt = status?.current_segment_judge_attempt;
  const current_segment_judge_substep = status?.current_segment_judge_substep;

  return (
    <div
      className="stage-detail-panel"
      style={{
        marginTop: 'var(--space-3)',
        padding: 'var(--space-3)',
        background: 'var(--bg-secondary)',
        borderRadius: 'var(--radius-lg)',
        border: '1px solid var(--border-light)',
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--space-2)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', flexWrap: 'wrap' }}>
        <StageBadge stage={current_stage} label={t(`stage.${current_stage}`)} />
        {current_stage === 'judge' && current_segment_judge_tier && (
          <JudgeTierBadge tier={current_segment_judge_tier} />
        )}
        {current_stage === 'judge' && current_segment_judge_attempt != null && (
          <span className="judge-attempt-counter" style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
            {current_segment_judge_attempt} / {JUDGE_MAX_ITERATIONS_DISPLAY}
          </span>
        )}
        {current_stage === 'judge' && current_segment_judge_substep && (
          <span className="judge-substep-label" style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
            {t(`stage.substep.${current_segment_judge_substep}`)}
          </span>
        )}
      </div>
      {current_segment_source && (
        <p className="stage-source" style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', margin: 0 }}>
          {current_segment_source}
        </p>
      )}
      {current_segment_draft && (
        <p className="stage-draft" style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)', margin: 0 }}>
          {current_segment_draft}
        </p>
      )}
      {current_segment_qe_score != null && (
        <p className="stage-qe-score" style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', margin: 0 }}>
          QE: {current_segment_qe_score.toFixed(3)}
        </p>
      )}
      {current_segment_adopted != null && (
        <p className="stage-adopted" style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', margin: 0 }}>
          {current_segment_adopted ? '✓' : '—'}
        </p>
      )}
    </div>
  );
}

export function TranslationProgress({ status }) {
  const { t } = useTranslation();
  if (!status) return null;
  const {
    overall_progress = 0,
    current_file = '',
    segments_done = 0,
    segments_total = 0,
    segments_per_second = 0,
    eta_seconds,
    provider,
    quality_score_avg,
    audit_hit_rate,
    status_detail,
  } = status;

  const isComplete = status.status === 'completed';
  const isFailed = status.status === 'failed';

  return (
    <div className="translation-progress">
      {/* Progress bar */}
      <div className="progress-bar-wrapper">
        <div className="progress-bar" style={{ width: `${Math.round(overall_progress * 100)}%` }} />
      </div>
      <p className="progress-pct">{Math.round(overall_progress * 100)}% 完成</p>

      {/* In-flight details */}
      {!isComplete && !isFailed && (
        <div className="progress-details">
          {status_detail && (
            <p className="progress-stage" style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{status_detail}</p>
          )}
          {current_file && <p className="progress-file">正在處理：{current_file}</p>}
          {segments_total > 0 && (
            <p className="progress-segs">{segments_done} / {segments_total} 段</p>
          )}
          {segments_per_second > 0 && (
            <p className="progress-speed">{segments_per_second.toFixed(1)} 段/秒</p>
          )}
          {eta_seconds != null && eta_seconds > 0 && (
            <p className="progress-eta">預計剩餘 {Math.ceil(eta_seconds)}s</p>
          )}
          {/* AC-4: current_stage remains visible (e.g. "critique") even when
              segments_done==segments_total, signalling post-translate work
              (critique/QE/judge) is still in progress — isComplete is driven
              by status.status, never by segment counts. */}
          <StageDetailPanel status={status} t={t} />
        </div>
      )}

      {/* Completion results panel */}
      {isComplete && (
        <div className="completion-panel">
          {provider && (
            <div className="result-row">
              <span className="result-label">翻譯引擎</span>
              <span className="result-value provider-badge">{provider}</span>
            </div>
          )}
          {quality_score_avg != null && (() => {
            const tier = qualityTier(quality_score_avg);
            return (
              <div className="result-row">
                <span className="result-label">COMET 品質評分</span>
                <span className="result-value" style={{ color: `var(${tier.colorVar})` }}>
                  {quality_score_avg.toFixed(3)} — {tier.label}
                </span>
              </div>
            );
          })()}
          {audit_hit_rate != null && (
            <div className="result-row">
              <span className="result-label">術語命中率</span>
              <span className="result-value">{(audit_hit_rate * 100).toFixed(1)}%</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
