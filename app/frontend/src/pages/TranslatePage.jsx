import React, { useReducer, useState, useEffect, useCallback } from 'react';
import { toast } from 'sonner';
import { StepWizard } from '../components/domain/StepWizard.jsx';
import { FileDropZone } from '../components/domain/FileDropZone.jsx';
import { FileCard } from '../components/domain/FileCard.jsx';
import { LanguageGrid } from '../components/domain/LanguageGrid.jsx';
import { RouteInfoDisplay } from '../components/domain/RouteInfoDisplay.jsx';
import { TranslationProgress } from '../components/domain/TranslationProgress.jsx';
import { Button } from '../components/ui/Button.jsx';
import { Select } from '../components/ui/Select.jsx';
import { useJobPolling } from '../hooks/useJobPolling.js';
import { useLocalStorage } from '../hooks/useLocalStorage.js';
import { useSettings } from '../contexts/SettingsContext.jsx';
import { createJob, cancelJob, getJudge } from '../api/jobs.js';
import { ALL_LANGUAGES } from '../constants/languages.js';
import { DEFAULT_SRC_LANG, DEFAULT_PROFILE, HISTORY_MAX_ENTRIES } from '../constants/defaults.js';
import { LayoutViewer } from '../components/domain/LayoutViewer.jsx';
import { JudgePanel } from '../components/domain/JudgePanel.jsx';

const STEPS = [
  { id: 'upload', label: '上傳檔案' },
  { id: 'settings', label: '語言與設定' },
  { id: 'progress', label: '翻譯進度' },
];

const initialState = {
  step: 1,
  files: [],
  selectedTargets: [],
  selectedProfile: DEFAULT_PROFILE,
  jobMode: 'translate',
  enableTermExtraction: true,
  pdfOutputFormat: 'docx',
  pdfLayoutMode: 'overlay',
  outputMode: 'append',
  jobId: null,
  jobStatus: null,
  error: null,
  loading: false,
};

const ACTIVE_JOB_KEY = 'activeJobId';

function makeInitialState() {
  let srcLang = DEFAULT_SRC_LANG;
  try { srcLang = JSON.parse(localStorage.getItem('defaultSrcLang')) || DEFAULT_SRC_LANG; } catch {}
  let selectedTargets = [];
  try { selectedTargets = JSON.parse(localStorage.getItem('defaultTargets')) || []; } catch {}
  // Restore in-progress job so navigating away and back keeps progress visible
  let jobId = null;
  try { jobId = localStorage.getItem(ACTIVE_JOB_KEY) || null; } catch {}
  const step = jobId ? 3 : 1;
  return { ...initialState, srcLang, selectedTargets, jobId, step };
}

function reducer(state, action) {
  switch (action.type) {
    case 'ADD_FILES': return { ...state, files: [...state.files, ...action.payload.filter(f => !state.files.find(e => e.name === f.name))] };
    case 'REMOVE_FILE': return { ...state, files: state.files.filter((_, i) => i !== action.payload) };
    case 'SET_TARGETS': return { ...state, selectedTargets: action.payload };
    case 'SET_SRC_LANG': return { ...state, srcLang: action.payload };
    case 'SET_PROFILE': return { ...state, selectedProfile: action.payload };
    case 'SET_MODE': return { ...state, jobMode: action.payload };
    case 'SET_ENABLE_TERM': return { ...state, enableTermExtraction: action.payload };
    case 'SET_PDF_OUTPUT': return { ...state, pdfOutputFormat: action.payload.format, pdfLayoutMode: action.payload.mode };
    case 'SET_OUTPUT_MODE': return { ...state, outputMode: action.payload };
    case 'SET_STEP': return { ...state, step: action.payload };
    case 'SET_JOB_ID': {
      try { if (action.payload) localStorage.setItem(ACTIVE_JOB_KEY, action.payload); } catch {}
      return { ...state, jobId: action.payload };
    }
    case 'SET_JOB_STATUS': return { ...state, jobStatus: action.payload };
    case 'SET_ERROR': return { ...state, error: action.payload };
    case 'SET_LOADING': return { ...state, loading: action.payload };
    case 'RESET': {
      try { localStorage.removeItem(ACTIVE_JOB_KEY); } catch {}
      return { ...initialState };
    }
    default: return state;
  }
}

export default function TranslatePage() {
  const [state, dispatch] = useReducer(reducer, null, makeInitialState);
  const [showLayout, setShowLayout] = useState(false);
  const [judgeData, setJudgeData] = useState(null);
  const { state: settings } = useSettings();
  const [history, setHistory] = useLocalStorage('translationHistory', []);

  const { step, files, selectedTargets, srcLang, selectedProfile, jobMode, enableTermExtraction, pdfOutputFormat, pdfLayoutMode, outputMode, jobId, jobStatus, loading } = state;
  const isTranslating = jobStatus && !['completed', 'failed', 'cancelled'].includes(jobStatus.status);
  const replaceUnsupported = selectedTargets.length > 1 ||
    files.some(f => /\.(pdf|xlsx?)$/i.test(f.name));

  // Fetch judge data once when job reaches completed status
  useEffect(() => {
    if (jobStatus?.status === 'completed' && jobId) {
      getJudge(jobId).then(setJudgeData).catch(() => {});
    }
  }, [jobId, jobStatus?.status]);

  function handleJobUpdate(data) {
    dispatch({ type: 'SET_JOB_STATUS', payload: data });
    if (data.status === 'completed') {
      const fileCount = files.length;
      toast.success(`翻譯完成，共 ${fileCount} 個檔案已就緒`);
      const entry = { jobId: data.job_id, fileCount, targets: selectedTargets, status: 'completed', completedAt: Date.now(), duration: data.duration_seconds };
      setHistory(prev => [entry, ...prev].slice(0, HISTORY_MAX_ENTRIES));
    } else if (data.status === 'failed') {
      toast.error(data.error || '翻譯失敗', { duration: Infinity });
      setHistory(prev => [{ jobId: data.job_id, fileCount: files.length, targets: selectedTargets, status: 'failed', completedAt: Date.now() }, ...prev].slice(0, HISTORY_MAX_ENTRIES));
    }
  }

  useJobPolling(jobId, handleJobUpdate, () => dispatch({ type: 'RESET' }));

  async function handleSubmit() {
    dispatch({ type: 'SET_LOADING', payload: true });
    try {
      const form = new FormData();
      files.forEach(f => form.append('files', f));
      form.append('targets', selectedTargets.join(','));
      form.append('src_lang', srcLang);
      form.append('profile', selectedProfile);
      form.append('mode', jobMode);
      form.append('enable_term_extraction', String(enableTermExtraction));
      const hasPdf = files.some(f => f.name.toLowerCase().endsWith('.pdf'));
      if (hasPdf) {
        form.append('pdf_output_format', pdfOutputFormat);
        form.append('pdf_layout_mode', pdfLayoutMode);
      }
      const hasXlsx = files.some(f => /\.xlsx?$/i.test(f.name));
      const effectiveOutputMode =
        (selectedTargets.length > 1 || hasPdf || hasXlsx) ? 'append' : outputMode;
      form.append('output_mode', effectiveOutputMode);
      const data = await createJob(form);
      dispatch({ type: 'SET_JOB_ID', payload: data.job_id });
      dispatch({ type: 'SET_STEP', payload: 3 });
    } catch (err) {
      toast.error(err.message, { duration: Infinity });
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  }

  async function handleCancel() {
    if (!jobId) return;
    try {
      await cancelJob(jobId);
      toast.info('翻譯已取消');
    } catch (err) {
      toast.error(err.message);
    }
  }

  function handleStepClick(s) {
    if (isTranslating) {
      toast.warning('翻譯進行中，請等待完成或取消後再切換');
      return;
    }
    dispatch({ type: 'SET_STEP', payload: s });
  }

  const handleJudgeApplyRequested = useCallback(() => {
    // Re-fetch judge data after apply so panel reflects new state;
    // useJobPolling already updates jobStatus (download_url, judge_apply_status) on its interval.
    if (jobId) {
      getJudge(jobId).then(setJudgeData).catch(() => {});
    }
  }, [jobId]);

  const profileOptions = settings.profiles.map(p => ({ value: p.id, label: `${p.name} — ${p.description}` }));
  const srcLangOptions = [{ value: 'auto', label: '自動偵測' }, ...ALL_LANGUAGES.slice(1).map(l => ({ value: l, label: l }))];

  return (
    <div className="translate-page">
      <StepWizard steps={STEPS} currentStep={step} onStepClick={handleStepClick} locked={isTranslating} />

      {step === 1 && (
        <div className="step-content">
          <FileDropZone onFilesAdded={newFiles => dispatch({ type: 'ADD_FILES', payload: newFiles })} />
          {files.length > 0 && (
            <div className="file-list">
              {files.map((f, i) => <FileCard key={i} file={f} onRemove={() => dispatch({ type: 'REMOVE_FILE', payload: i })} />)}
            </div>
          )}
          <div className="step-actions">
            <Button disabled={files.length === 0} onClick={() => dispatch({ type: 'SET_STEP', payload: 2 })}>下一步</Button>
          </div>
        </div>
      )}

      {step === 2 && (
        <div className="step-content step-2-layout">
          <div className="step-2-left">
            <h3>目標語言</h3>
            <LanguageGrid selected={selectedTargets} onChange={targets => dispatch({ type: 'SET_TARGETS', payload: targets })} />
            <RouteInfoDisplay targets={selectedTargets} />
          </div>
          <div className="step-2-right">
            <div className="mode-toggle">
              <button className={`mode-btn ${jobMode === 'translate' ? 'mode-btn-active' : ''}`} onClick={() => dispatch({ type: 'SET_MODE', payload: 'translate' })}>翻譯</button>
              <button className={`mode-btn ${jobMode === 'extraction_only' ? 'mode-btn-active' : ''}`} onClick={() => dispatch({ type: 'SET_MODE', payload: 'extraction_only' })}>僅萃取術語</button>
            </div>
            <Select label="來源語言" options={srcLangOptions} value={srcLang} onChange={e => dispatch({ type: 'SET_SRC_LANG', payload: e.target.value })} />
            <Select label="翻譯情境" options={profileOptions} value={selectedProfile} onChange={e => dispatch({ type: 'SET_PROFILE', payload: e.target.value })} />
            {jobMode === 'translate' && (
              <Select
                label="輸出方式"
                options={replaceUnsupported
                  ? [{ value: 'append', label: '原文在下方（多目標或 PDF/XLSX 不支援取代）' }]
                  : [
                      { value: 'append', label: '原文在下方' },
                      { value: 'replace', label: '原地取代/覆蓋原文' },
                    ]}
                value={replaceUnsupported ? 'append' : outputMode}
                onChange={e => dispatch({ type: 'SET_OUTPUT_MODE', payload: e.target.value })}
              />
            )}
            {jobMode === 'translate' && (
              <label style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', cursor: 'pointer', marginTop: 'var(--space-3)' }}>
                <input
                  type="checkbox"
                  checked={enableTermExtraction}
                  onChange={e => dispatch({ type: 'SET_ENABLE_TERM', payload: e.target.checked })}
                  style={{ width: 16, height: 16, cursor: 'pointer' }}
                />
                啟用術語抽取與注入
              </label>
            )}
            {jobMode === 'translate' && files.some(f => f.name.toLowerCase().endsWith('.pdf')) && (
              <div style={{ marginTop: 'var(--space-4)' }}>
                <div style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 'var(--space-2)' }}>PDF 輸出格式</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
                  {[
                    { format: 'docx', mode: 'overlay', label: 'DOCX', desc: '匯出為 Word 文件（最高相容性）' },
                    { format: 'pdf', mode: 'overlay', label: 'PDF 疊加', desc: '譯文貼回原始 PDF 版面' },
                    { format: 'pdf', mode: 'side_by_side', label: 'PDF 對照', desc: '原文 ｜ 譯文左右並排' },
                  ].map(opt => (
                    <label key={opt.label} style={{ display: 'flex', alignItems: 'flex-start', gap: 'var(--space-2)', cursor: 'pointer' }}>
                      <input
                        type="radio"
                        name="pdfOutput"
                        checked={pdfOutputFormat === opt.format && pdfLayoutMode === opt.mode}
                        onChange={() => dispatch({ type: 'SET_PDF_OUTPUT', payload: { format: opt.format, mode: opt.mode } })}
                        style={{ marginTop: 2, cursor: 'pointer' }}
                      />
                      <span>
                        <span style={{ fontSize: 'var(--text-sm)', fontWeight: 500, color: 'var(--text-primary)' }}>{opt.label}</span>
                        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', display: 'block' }}>{opt.desc}</span>
                      </span>
                    </label>
                  ))}
                </div>
              </div>
            )}
          </div>
          <div className="step-actions">
            <Button variant="secondary" onClick={() => dispatch({ type: 'SET_STEP', payload: 1 })}>上一步</Button>
            <Button disabled={selectedTargets.length === 0 || loading} onClick={handleSubmit}>
              {loading ? '提交中...' : jobMode === 'extraction_only' ? '開始萃取' : '開始翻譯'}
            </Button>
          </div>
        </div>
      )}

      {step === 3 && (
        <div className="step-content">
          <TranslationProgress status={jobStatus} />
          {jobStatus?.status === 'extraction_only_completed' && (
            <div className="extraction-result">
              <p>已萃取 {jobStatus.terms_extracted} 個術語</p>
              <a href="/terms/review" className="btn btn-primary">前往術語庫審核</a>
            </div>
          )}
          {jobStatus?.layout_viz_available && (
            <div style={{ marginTop: 'var(--space-4)' }}>
              <button
                className="btn btn-secondary"
                style={{ fontSize: 'var(--text-sm)' }}
                onClick={() => setShowLayout(v => !v)}
              >
                {showLayout ? '隱藏版面偵測' : '查看版面偵測結果'}
              </button>
              {showLayout && (
                <div style={{ marginTop: 'var(--space-4)', padding: 'var(--space-4)', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-lg)', border: '1px solid var(--border-light)' }}>
                  <LayoutViewer jobId={jobId} onClose={() => setShowLayout(false)} />
                </div>
              )}
            </div>
          )}
          <JudgePanel
            judgeData={judgeData}
            jobId={jobId}
            judgeApplyStatus={jobStatus?.judge_apply_status}
            onApplyRequested={handleJudgeApplyRequested}
          />

          <div className="step-actions">
            {isTranslating && <Button variant="danger" onClick={handleCancel}>取消翻譯</Button>}
            {jobStatus?.status === 'completed' && (
              <>
                {jobStatus.download_url && <a className="btn btn-primary" href={jobStatus.download_url} download>下載譯文</a>}
                <Button variant="secondary" onClick={() => { dispatch({ type: 'RESET' }); setShowLayout(false); setJudgeData(null); }}>開始新翻譯</Button>
              </>
            )}
            {jobStatus?.status === 'failed' && <Button variant="secondary" onClick={() => dispatch({ type: 'RESET' })}>重新開始</Button>}
          </div>
        </div>
      )}
    </div>
  );
}
