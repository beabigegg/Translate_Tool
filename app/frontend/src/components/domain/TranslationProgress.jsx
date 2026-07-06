import React from 'react';

function qualityTier(score) {
  if (score >= 0.85) return { label: '高品質', color: '#22c55e' };
  if (score >= 0.70) return { label: '良好', color: '#84cc16' };
  if (score >= 0.55) return { label: '可接受', color: '#f59e0b' };
  return { label: '需審校', color: '#ef4444' };
}

export function TranslationProgress({ status }) {
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
    warnings,
    layout_qa,
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
                <span className="result-value" style={{ color: tier.color }}>
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
          {Array.isArray(layout_qa) && layout_qa.length > 0 && layout_qa.map((qa, i) => (
            <div className="result-row" key={`${qa.file}-${qa.target_lang}-${i}`}>
              <span className="result-label">版面 QA（{qa.target_lang}）</span>
              <span className="result-value" style={{ color: qa.passed ? '#22c55e' : '#f59e0b' }}>
                {qa.passed ? '通過' : '需檢視'}
                {qa.biou != null && ` ・BIoU ${qa.biou.toFixed(2)}`}
                {qa.truncated_blocks > 0 && ` ・截斷 ${qa.truncated_blocks}/${qa.total_blocks} 區塊`}
                {qa.residual_text_blocks > 0 && ` ・殘留原文 ${qa.residual_text_blocks} 區塊`}
              </span>
            </div>
          ))}
          {Array.isArray(warnings) && warnings.length > 0 && (
            <div className="result-row" style={{ flexDirection: 'column', alignItems: 'flex-start' }}>
              <span className="result-label">注意事項</span>
              {warnings.map((w, i) => (
                <span className="result-value" key={i} style={{ color: '#f59e0b', fontSize: '0.85em' }}>⚠ {w}</span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
