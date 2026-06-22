import React, { useEffect, useRef } from 'react';

/**
 * JudgeApplyDialog — Modal confirming destructive overwrite of the translated output
 * with the judge's re-translated text.
 *
 * Props:
 *   isOpen         {boolean}   whether the dialog is visible
 *   previewText    {string}    re-translated text to preview
 *   onConfirm      {Function}  async callback; fires POST /api/jobs/{id}/judge/apply
 *   onCancel       {Function}  closes dialog with no side effect
 */
export function JudgeApplyDialog({ isOpen, previewText, onConfirm, onCancel }) {
  const cancelBtnRef = useRef(null);
  const confirmBtnRef = useRef(null);

  useEffect(() => {
    if (!isOpen) return;
    // Move focus to cancel button on open
    cancelBtnRef.current?.focus();
    // Escape closes; Tab wraps between the two action buttons
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') { onCancel(); return; }
      if (e.key === 'Tab') {
        if (e.shiftKey) {
          if (document.activeElement === cancelBtnRef.current) {
            e.preventDefault();
            confirmBtnRef.current?.focus();
          }
        } else {
          if (document.activeElement === confirmBtnRef.current) {
            e.preventDefault();
            cancelBtnRef.current?.focus();
          }
        }
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onCancel]);

  if (!isOpen) return null;

  return (
    <div
      className="judge-apply-dialog-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="judge-apply-dialog-title"
      style={{
        position: 'fixed',
        inset: 0,
        background: 'var(--surface-overlay)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 'var(--z-modal)',
        padding: 'var(--space-4)',
      }}
    >
      <div
        className="judge-apply-dialog"
        style={{
          background: 'var(--bg-primary)',
          borderRadius: 'var(--radius-xl)',
          boxShadow: 'var(--shadow-xl)',
          padding: 'var(--space-6)',
          maxWidth: 'min(560px, calc(100vw - var(--space-8, 2rem)))',
          width: '100%',
          display: 'flex',
          flexDirection: 'column',
          gap: 'var(--space-4)',
        }}
      >
        <h2
          id="judge-apply-dialog-title"
          style={{
            margin: 0,
            fontSize: 'var(--text-lg)',
            fontWeight: 600,
            color: 'var(--text-primary)',
          }}
        >
          套用 LLM 裁判重譯結果
        </h2>

        {previewText && (
          <div
            style={{
              background: 'var(--bg-secondary)',
              borderRadius: 'var(--radius-lg)',
              padding: 'var(--space-4)',
              fontSize: 'var(--text-sm)',
              color: 'var(--text-secondary)',
              lineHeight: 'var(--leading-relaxed)',
              maxHeight: 200,
              overflowY: 'auto',
              border: '1px solid var(--border-light)',
            }}
            aria-label="重譯預覽"
          >
            <div style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-muted)', marginBottom: 'var(--space-2)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              重譯預覽
            </div>
            {previewText}
          </div>
        )}

        <div
          className="judge-apply-dialog-warning"
          role="alert"
          style={{
            background: 'var(--error-light)',
            border: '1px solid var(--error)',
            borderRadius: 'var(--radius-lg)',
            padding: 'var(--space-3) var(--space-4)',
            fontSize: 'var(--text-sm)',
            color: 'var(--error-dark)',
            fontWeight: 500,
          }}
        >
          注意：目前的下載檔案將被覆蓋，且不會建立備份。此操作無法復原。
        </div>

        <div
          style={{
            display: 'flex',
            gap: 'var(--space-3)',
            justifyContent: 'flex-end',
          }}
        >
          <button
            ref={cancelBtnRef}
            type="button"
            onClick={onCancel}
            style={{
              padding: 'var(--space-2) var(--space-5)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-default)',
              background: 'var(--bg-primary)',
              color: 'var(--text-secondary)',
              fontSize: 'var(--text-sm)',
              fontWeight: 500,
              cursor: 'pointer',
            }}
          >
            取消
          </button>
          <button
            ref={confirmBtnRef}
            type="button"
            onClick={onConfirm}
            style={{
              padding: 'var(--space-2) var(--space-5)',
              borderRadius: 'var(--radius-md)',
              border: 'none',
              background: 'var(--error)',
              color: 'var(--text-inverse)',
              fontSize: 'var(--text-sm)',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            確認套用
          </button>
        </div>
      </div>
    </div>
  );
}
