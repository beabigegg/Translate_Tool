import React, { useMemo, useRef, useState } from 'react';

// Stable per-language color without knowing the full language set up front
// (a multilingual meeting can surface any ISO code) — hash the code into a
// fixed palette instead of maintaining a lookup table like LayoutViewer's
// TYPE_COLORS (which is closed-set by design).
const LANGUAGE_PALETTE = ['#3b82f6', '#8b5cf6', '#f59e0b', '#10b981', '#ef4444', '#06b6d4', '#ec4899', '#84cc16'];

function languageColor(lang) {
  if (!lang) return null;
  let hash = 0;
  for (let i = 0; i < lang.length; i++) hash = (hash * 31 + lang.charCodeAt(i)) >>> 0;
  return LANGUAGE_PALETTE[hash % LANGUAGE_PALETTE.length];
}

function LanguageBadge({ language }) {
  const color = languageColor(language);
  if (!color) {
    return <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>—</span>;
  }
  return (
    <span
      className="language-badge"
      style={{
        display: 'inline-block',
        padding: 'var(--space-1) var(--space-2)',
        borderRadius: 'var(--radius-full)',
        fontSize: 'var(--text-xs)',
        fontWeight: 700,
        color: 'var(--text-inverse)',
        background: color,
      }}
    >
      {language.toUpperCase()}
    </span>
  );
}

function formatTimestamp(seconds, useHours) {
  const total = Math.max(0, Math.floor(seconds || 0));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const pad = n => String(n).padStart(2, '0');
  return useHours ? `${pad(h)}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`;
}

function SegmentRow({ segment, index, isActive, useHours, onSelect }) {
  const translations = useMemo(
    () => Object.entries(segment.translated_text || {}).sort((a, b) => a[0].localeCompare(b[0])),
    [segment.translated_text]
  );

  return (
    <tr
      className="transcript-segment-row"
      role="button"
      tabIndex={0}
      onClick={() => onSelect(index)}
      onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(index); } }}
      style={{
        cursor: 'pointer',
        background: isActive ? 'var(--primary-50)' : 'transparent',
        borderBottom: '1px solid var(--border-light)',
      }}
    >
      <td style={{ padding: 'var(--space-2) var(--space-3)', fontSize: 'var(--text-xs)', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)', whiteSpace: 'nowrap', verticalAlign: 'top' }}>
        {formatTimestamp(segment.start, useHours)} - {formatTimestamp(segment.end, useHours)}
      </td>
      <td style={{ padding: 'var(--space-2) var(--space-3)', verticalAlign: 'top' }}>
        <LanguageBadge language={segment.language} />
      </td>
      <td style={{ padding: 'var(--space-2) var(--space-3)', fontSize: 'var(--text-sm)', color: 'var(--text-primary)', verticalAlign: 'top' }}>
        {segment.text}
      </td>
      <td style={{ padding: 'var(--space-2) var(--space-3)', fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', verticalAlign: 'top' }}>
        {translations.length === 0 ? (
          <span style={{ color: 'var(--text-muted)' }}>—</span>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
            {translations.map(([lang, text]) => (
              <div key={lang} style={{ display: 'flex', gap: 'var(--space-2)', alignItems: 'baseline' }}>
                <span style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-muted)', flexShrink: 0 }}>
                  {lang.toUpperCase()}
                </span>
                <span>{text}</span>
              </div>
            ))}
          </div>
        )}
      </td>
    </tr>
  );
}

/**
 * Props:
 *   transcript {TranscriptResponse|null} GET /api/media/jobs/{id}/transcript response — { job_id, duration, segments }
 *   mediaUrl   {string|null}             object URL (or served URL) for local playback of the source upload
 *   mediaKind  {'audio'|'video'}         which element to render for playback (default 'audio')
 */
export function TranscriptViewer({ transcript, mediaUrl, mediaKind = 'audio' }) {
  const mediaRef = useRef(null);
  const [currentTime, setCurrentTime] = useState(0);

  const segments = transcript?.segments ?? [];
  const useHours = (transcript?.duration ?? 0) >= 3600;

  const activeIndex = useMemo(() => {
    return segments.findIndex(seg => currentTime >= seg.start && currentTime < seg.end);
  }, [segments, currentTime]);

  function handleSelect(index) {
    const seg = segments[index];
    const el = mediaRef.current;
    if (!seg || !el) return;
    el.currentTime = seg.start;
    const playPromise = el.play();
    if (playPromise && typeof playPromise.catch === 'function') playPromise.catch(() => {});
  }

  if (!transcript) return null;

  const MediaTag = mediaKind === 'video' ? 'video' : 'audio';

  return (
    <div className="transcript-viewer" style={{ fontFamily: 'var(--font-sans)' }}>
      {mediaUrl && (
        <MediaTag
          ref={mediaRef}
          src={mediaUrl}
          controls
          onTimeUpdate={e => setCurrentTime(e.currentTarget.currentTime)}
          style={{
            width: '100%',
            maxHeight: mediaKind === 'video' ? 360 : undefined,
            marginBottom: 'var(--space-4)',
            borderRadius: 'var(--radius-lg)',
            background: mediaKind === 'video' ? '#000' : undefined,
          }}
        />
      )}

      {segments.length === 0 ? (
        <p style={{ color: 'var(--text-muted)', fontSize: 'var(--text-sm)' }}>此工作尚無逐字稿分段</p>
      ) : (
        <div style={{ border: '1px solid var(--border-light)', borderRadius: 'var(--radius-lg)', maxHeight: 480, overflowY: 'auto', overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }} role="table">
            <thead>
              <tr style={{ position: 'sticky', top: 0, background: 'var(--bg-secondary)', zIndex: 1 }}>
                <th style={{ textAlign: 'left', padding: 'var(--space-2) var(--space-3)', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', borderBottom: '1px solid var(--border-light)' }}>時間</th>
                <th style={{ textAlign: 'left', padding: 'var(--space-2) var(--space-3)', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', borderBottom: '1px solid var(--border-light)' }}>語言</th>
                <th style={{ textAlign: 'left', padding: 'var(--space-2) var(--space-3)', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', borderBottom: '1px solid var(--border-light)' }}>原文</th>
                <th style={{ textAlign: 'left', padding: 'var(--space-2) var(--space-3)', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', borderBottom: '1px solid var(--border-light)' }}>譯文</th>
              </tr>
            </thead>
            <tbody>
              {segments.map((segment, index) => (
                <SegmentRow
                  key={`${segment.start}-${index}`}
                  segment={segment}
                  index={index}
                  isActive={index === activeIndex}
                  useHours={useHours}
                  onSelect={handleSelect}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
