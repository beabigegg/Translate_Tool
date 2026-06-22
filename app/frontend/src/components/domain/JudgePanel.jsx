import React, { useState } from 'react';
import { JudgeApplyDialog } from './JudgeApplyDialog.jsx';
import { applyJudge } from '../../api/jobs.js';

/**
 * Map a score tier to its CSS variable name.
 * Returns the variable reference string (not a hex value).
 */
function scoreColor(score) {
  if (score === '高') return 'var(--color-quality-high)';
  if (score === '中') return 'var(--color-quality-mid)';
  if (score === '低') return 'var(--color-quality-low)';
  return 'var(--text-muted)';
}

/**
 * JudgeBadge — inline badge showing score tier with token-based colour.
 * Color is always via CSS vars; hardcoded hex is forbidden.
 */
function JudgeBadge({ score }) {
  return (
    <span
      className="judge-badge"
      style={{
        display: 'inline-block',
        padding: 'var(--space-1) var(--space-3)',
        borderRadius: 'var(--radius-full)',
        fontSize: 'var(--text-sm)',
        fontWeight: 700,
        color: 'var(--text-inverse)',
        background: scoreColor(score),
        letterSpacing: '0.05em',
      }}
    >
      {score}
    </span>
  );
}

/**
 * JudgePanel — renders judge results when judge_status === "available".
 * Renders NOTHING (clean absence) for any other status.
 *
 * Props:
 *   judgeData         {object|null}  full response from GET /api/jobs/{id}/judge
 *   jobId             {string}       job identifier
 *   judgeApplyStatus  {string|null}  from jobStatus.judge_apply_status (polled by TranslatePage)
 *   onApplyRequested  {Function}     callback invoked after successful applyJudge POST
 */
export function JudgePanel({ judgeData, jobId, judgeApplyStatus, onApplyRequested }) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [applyError, setApplyError] = useState(null);

  // CSS contract: render nothing when judge_status !== "available"
  if (!judgeData || judgeData.judge_status !== 'available') {
    return null;
  }

  const { score, source_text, translated_text, feedback, attempts, model } = judgeData;

  // CSS contract: button visible only when score ∈ {中, 低} AND
  // judge_apply_status ∉ {applying, applied}
  const showApplyButton =
    (score === '中' || score === '低') &&
    judgeApplyStatus !== 'applying' &&
    judgeApplyStatus !== 'applied';

  // CSS contract: button disabled when applying or applied
  const applyButtonDisabled =
    judgeApplyStatus === 'applying' || judgeApplyStatus === 'applied';

  // CSS contract: re-enable with retry affordance when failed
  const isRetry = judgeApplyStatus === 'failed';

  async function handleConfirm() {
    setApplyError(null);
    try {
      await applyJudge(jobId);
      setDialogOpen(false);
      onApplyRequested?.();
    } catch (err) {
      setApplyError(err.message || '套用失敗');
      setDialogOpen(false);
    }
  }

  return (
    <div
      className="judge-panel"
      style={{
        marginTop: 'var(--space-4)',
        padding: 'var(--space-4)',
        background: 'var(--bg-secondary)',
        borderRadius: 'var(--radius-xl)',
        border: '1px solid var(--border-light)',
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--space-3)',
      }}
    >
      {/* Header row: label + badge */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
        <span style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--text-secondary)' }}>
          LLM 裁判評分
        </span>
        <JudgeBadge score={score} />
        {attempts != null && (
          <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', marginLeft: 'auto' }}>
            {attempts} 次迭代
            {model ? ` · ${model}` : ''}
          </span>
        )}
      </div>

      {/* Source text */}
      {source_text && (
        <div>
          <div style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-muted)', marginBottom: 'var(--space-1)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            原文
          </div>
          <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', lineHeight: 'var(--leading-relaxed)', background: 'var(--bg-primary)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-3)', border: '1px solid var(--border-light)' }}>
            {source_text}
          </div>
        </div>
      )}

      {/* Translated text (judge's accepted draft) */}
      {translated_text && (
        <div>
          <div style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-muted)', marginBottom: 'var(--space-1)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            裁判譯文（預覽）
          </div>
          <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', lineHeight: 'var(--leading-relaxed)', background: 'var(--bg-primary)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-3)', border: '1px solid var(--border-light)' }}>
            {translated_text}
          </div>
        </div>
      )}

      {/* Feedback */}
      {feedback && (
        <div>
          <div style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-muted)', marginBottom: 'var(--space-1)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            裁判意見
          </div>
          <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', lineHeight: 'var(--leading-relaxed)', fontStyle: 'italic' }}>
            {feedback}
          </div>
        </div>
      )}

      {/* Apply status indicator */}
      {judgeApplyStatus === 'applied' && (
        <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-quality-high)', fontWeight: 500 }}>
          已成功套用裁判重譯結果
        </div>
      )}
      {judgeApplyStatus === 'applying' && (
        <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)' }}>
          正在套用中...
        </div>
      )}
      {applyError && (
        <div style={{ fontSize: 'var(--text-sm)', color: 'var(--error)', fontWeight: 500 }}>
          套用失敗：{applyError}
        </div>
      )}

      {/* JudgeApplyButton */}
      {showApplyButton && (
        <button
          type="button"
          className="judge-apply-button"
          disabled={applyButtonDisabled}
          onClick={() => setDialogOpen(true)}
          style={{
            width: '100%',
            padding: 'var(--space-2) var(--space-4)',
            borderRadius: 'var(--radius-md)',
            border: 'none',
            background: applyButtonDisabled ? 'var(--border-default)' : 'var(--primary)',
            color: 'var(--text-inverse)',
            fontSize: 'var(--text-sm)',
            fontWeight: 600,
            cursor: applyButtonDisabled ? 'not-allowed' : 'pointer',
            opacity: applyButtonDisabled ? 0.6 : 1,
          }}
          aria-label={isRetry ? '重試套用裁判重譯結果' : '套用裁判重譯結果'}
        >
          {isRetry ? '重試套用' : '套用裁判重譯'}
        </button>
      )}

      {/* Apply dialog */}
      <JudgeApplyDialog
        isOpen={dialogOpen}
        previewText={translated_text}
        onConfirm={handleConfirm}
        onCancel={() => setDialogOpen(false)}
      />
    </div>
  );
}
