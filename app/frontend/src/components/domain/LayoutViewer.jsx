import React, { useState, useEffect } from 'react';
import { getLayoutViz } from '../../api/layout.js';

const TYPE_COLORS = {
  text: '#3b82f6',
  list_item: '#3b82f6',
  caption: '#3b82f6',
  footnote: '#3b82f6',
  title: '#8b5cf6',
  header: '#6b7280',
  footer: '#6b7280',
  table: '#f59e0b',
  table_cell: '#f59e0b',
  figure: '#10b981',
  formula: '#ef4444',
};

const LEGEND_ENTRIES = [
  { label: '文字 / 清單 / 說明', color: '#3b82f6' },
  { label: '標題', color: '#8b5cf6' },
  { label: '頁首 / 頁尾', color: '#6b7280' },
  { label: '表格', color: '#f59e0b' },
  { label: '圖片', color: '#10b981' },
  { label: '公式', color: '#ef4444' },
];

const MAX_CANVAS_WIDTH = 520;
const API_BASE = import.meta.env.VITE_API_BASE ?? '';

// file_stem: filename without extension, used to construct the page image URL
function pageStem(fileName) {
  const dot = fileName.lastIndexOf('.');
  return dot > 0 ? fileName.slice(0, dot) : fileName;
}

function pageImageUrl(jobId, fileName, pageNum) {
  return `${API_BASE}/api/jobs/${jobId}/layout/page/${encodeURIComponent(pageStem(fileName))}/${pageNum}`;
}

function PageCanvas({ jobId, fileName, page }) {
  const aspectRatio = page.height / page.width;
  const canvasH = Math.round(MAX_CANVAS_WIDTH * aspectRatio);
  const imgUrl = pageImageUrl(jobId, fileName, page.page_num);

  return (
    <div style={{ display: 'flex', gap: 'var(--space-5)', alignItems: 'flex-start' }}>
      <div
        style={{
          position: 'relative',
          width: MAX_CANVAS_WIDTH,
          height: canvasH,
          background: '#f0f0f0',
          border: '1px solid var(--border-light)',
          borderRadius: 'var(--radius-sm)',
          flexShrink: 0,
          boxShadow: '0 1px 4px rgba(0,0,0,0.08)',
          overflow: 'hidden',
        }}
      >
        {/* Underlying page image */}
        <img
          src={imgUrl}
          alt=""
          style={{
            position: 'absolute',
            top: 0, left: 0,
            width: '100%',
            height: '100%',
            objectFit: 'fill',
          }}
          onError={e => { e.currentTarget.style.display = 'none'; }}
        />

        {/* Bounding box overlays */}
        {page.boxes.map((box, idx) => {
          const [x0, y0, x1, y1] = box.bbox;
          const color = TYPE_COLORS[box.type] || '#94a3b8';
          return (
            <div
              key={idx}
              title={`${box.type}${box.preview ? ': ' + box.preview : ''}${box.score < 1 ? ` (${(box.score * 100).toFixed(0)}%)` : ''}`}
              style={{
                position: 'absolute',
                left: `${x0 * 100}%`,
                top: `${y0 * 100}%`,
                width: `${Math.max((x1 - x0) * 100, 0.5)}%`,
                height: `${Math.max((y1 - y0) * 100, 0.5)}%`,
                border: `1.5px solid ${color}`,
                background: `${color}22`,
                boxSizing: 'border-box',
                cursor: 'help',
              }}
            />
          );
        })}
      </div>

      <div style={{ minWidth: 130 }}>
        <div style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 'var(--space-2)' }}>
          圖例
        </div>
        {LEGEND_ENTRIES.map(({ label, color }) => (
          <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-1)', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
            <div style={{ width: 12, height: 12, background: color, borderRadius: 2, flexShrink: 0 }} />
            {label}
          </div>
        ))}
      </div>
    </div>
  );
}

function FileViewer({ jobId, fileData }) {
  const [pageIdx, setPageIdx] = useState(0);

  useEffect(() => { setPageIdx(0); }, [fileData.file_name]);

  if (!fileData.pages || fileData.pages.length === 0) {
    return <p style={{ color: 'var(--text-muted)', fontSize: 'var(--text-sm)' }}>此檔案無版面偵測資料</p>;
  }

  const page = fileData.pages[Math.min(pageIdx, fileData.pages.length - 1)];

  return (
    <>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 'var(--space-4)', marginBottom: 'var(--space-3)' }}>
        <button
          onClick={() => setPageIdx(i => Math.max(0, i - 1))}
          disabled={pageIdx === 0}
          style={{ padding: '2px 10px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-light)', background: pageIdx === 0 ? 'var(--bg-secondary)' : 'var(--bg-primary)', cursor: pageIdx === 0 ? 'not-allowed' : 'pointer', color: pageIdx === 0 ? 'var(--text-muted)' : 'var(--text-primary)', fontSize: 'var(--text-sm)' }}
        >
          ‹ 上一頁
        </button>
        <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', minWidth: 80, textAlign: 'center' }}>
          頁 {page.page_num} / {fileData.total_pages}
        </span>
        <button
          onClick={() => setPageIdx(i => Math.min(fileData.pages.length - 1, i + 1))}
          disabled={pageIdx >= fileData.pages.length - 1}
          style={{ padding: '2px 10px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-light)', background: pageIdx >= fileData.pages.length - 1 ? 'var(--bg-secondary)' : 'var(--bg-primary)', cursor: pageIdx >= fileData.pages.length - 1 ? 'not-allowed' : 'pointer', color: pageIdx >= fileData.pages.length - 1 ? 'var(--text-muted)' : 'var(--text-primary)', fontSize: 'var(--text-sm)' }}
        >
          下一頁 ›
        </button>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', marginBottom: 'var(--space-3)', fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
        <span
          style={{
            padding: '2px 8px',
            borderRadius: 'var(--radius-full)',
            background: page.detector === 'onnx' ? '#d1fae5' : '#f3f4f6',
            color: page.detector === 'onnx' ? '#065f46' : '#6b7280',
            fontWeight: 600,
          }}
        >
          {page.detector === 'onnx' ? 'ONNX 神經網路' : page.detector === 'disabled' ? '停用' : '啟發式'}
        </span>
        <span>{page.boxes.length} 個區塊</span>
        <span>{Math.round(page.width)} × {Math.round(page.height)} pt</span>
      </div>

      <PageCanvas jobId={jobId} fileName={fileData.file_name} page={page} />
    </>
  );
}

export function LayoutViewer({ jobId, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [notAvailable, setNotAvailable] = useState(false);
  const [fileIdx, setFileIdx] = useState(0);

  useEffect(() => {
    if (!jobId) return;
    setLoading(true);
    setNotAvailable(false);
    setFileIdx(0);
    getLayoutViz(jobId)
      .then(d => {
        if (!d || !d.files || d.files.length === 0) { setNotAvailable(true); }
        else { setData(d); }
      })
      .catch(() => setNotAvailable(true))
      .finally(() => setLoading(false));
  }, [jobId]);

  if (loading) {
    return <div style={{ padding: 'var(--space-6)', textAlign: 'center', color: 'var(--text-muted)', fontSize: 'var(--text-sm)' }}>載入版面偵測資料...</div>;
  }
  if (notAvailable) {
    return <div style={{ padding: 'var(--space-6)', textAlign: 'center', color: 'var(--text-muted)', fontSize: 'var(--text-sm)' }}>此工作無版面偵測資料（僅 PDF 支援）</div>;
  }
  if (!data) return null;

  const files = data.files;
  const currentFile = files[Math.min(fileIdx, files.length - 1)];

  return (
    <div style={{ fontFamily: 'var(--font-sans)' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-4)' }}>
        <strong style={{ fontSize: 'var(--text-sm)', color: 'var(--text-primary)' }}>版面偵測結果</strong>
        {onClose && (
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 'var(--text-xl)', color: 'var(--text-muted)', lineHeight: 1 }} aria-label="關閉">×</button>
        )}
      </div>

      {files.length > 1 && (
        <div style={{ marginBottom: 'var(--space-4)', display: 'flex', flexWrap: 'wrap', gap: 'var(--space-2)' }}>
          {files.map((f, i) => (
            <button
              key={f.file_name}
              onClick={() => setFileIdx(i)}
              style={{
                padding: '3px 10px',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-light)',
                background: i === fileIdx ? 'var(--primary)' : 'var(--bg-secondary)',
                color: i === fileIdx ? '#fff' : 'var(--text-secondary)',
                cursor: 'pointer',
                fontSize: 'var(--text-xs)',
                fontWeight: i === fileIdx ? 600 : 400,
              }}
            >
              {f.file_name} <span style={{ opacity: 0.7 }}>({f.total_pages} 頁)</span>
            </button>
          ))}
        </div>
      )}

      {files.length === 1 && (
        <div style={{ marginBottom: 'var(--space-3)', fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
          {currentFile.file_name} · {currentFile.total_pages} 頁
        </div>
      )}

      <FileViewer jobId={jobId} fileData={currentFile} />
    </div>
  );
}
