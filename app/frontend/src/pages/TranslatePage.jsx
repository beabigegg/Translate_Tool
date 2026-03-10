import React, { useReducer } from 'react';
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
import { createJob, cancelJob } from '../api/jobs.js';
import { ALL_LANGUAGES } from '../constants/languages.js';
import { DEFAULT_SRC_LANG, DEFAULT_PROFILE, HISTORY_MAX_ENTRIES } from '../constants/defaults.js';

const STEPS = [
  { id: 'upload', label: '上傳檔案' },
  { id: 'settings', label: '語言與設定' },
  { id: 'progress', label: '翻譯進度' },
];

const initialState = {
  step: 1,
  files: [],
  selectedTargets: [],
  srcLang: DEFAULT_SRC_LANG,
  selectedProfile: DEFAULT_PROFILE,
  jobMode: 'translate',
  jobId: null,
  jobStatus: null,
  error: null,
  loading: false,
};

function reducer(state, action) {
  switch (action.type) {
    case 'ADD_FILES': return { ...state, files: [...state.files, ...action.payload.filter(f => !state.files.find(e => e.name === f.name))] };
    case 'REMOVE_FILE': return { ...state, files: state.files.filter((_, i) => i !== action.payload) };
    case 'SET_TARGETS': return { ...state, selectedTargets: action.payload };
    case 'SET_SRC_LANG': return { ...state, srcLang: action.payload };
    case 'SET_PROFILE': return { ...state, selectedProfile: action.payload };
    case 'SET_MODE': return { ...state, jobMode: action.payload };
    case 'SET_STEP': return { ...state, step: action.payload };
    case 'SET_JOB_ID': return { ...state, jobId: action.payload };
    case 'SET_JOB_STATUS': return { ...state, jobStatus: action.payload };
    case 'SET_ERROR': return { ...state, error: action.payload };
    case 'SET_LOADING': return { ...state, loading: action.payload };
    case 'RESET': return { ...initialState };
    default: return state;
  }
}

export default function TranslatePage() {
  const [state, dispatch] = useReducer(reducer, initialState);
  const { state: settings } = useSettings();
  const [history, setHistory] = useLocalStorage('translationHistory', []);

  const { step, files, selectedTargets, srcLang, selectedProfile, jobMode, jobId, jobStatus, loading } = state;
  const isTranslating = jobStatus && !['completed', 'failed', 'cancelled'].includes(jobStatus.status);

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

  useJobPolling(jobId, handleJobUpdate);

  async function handleSubmit() {
    dispatch({ type: 'SET_LOADING', payload: true });
    try {
      const form = new FormData();
      files.forEach(f => form.append('files', f));
      selectedTargets.forEach(t => form.append('target_langs', t));
      form.append('src_lang', srcLang);
      form.append('profile', selectedProfile);
      form.append('mode', jobMode);
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
          <div className="step-actions">
            {isTranslating && <Button variant="danger" onClick={handleCancel}>取消翻譯</Button>}
            {jobStatus?.status === 'completed' && (
              <>
                {jobStatus.download_url && <a className="btn btn-primary" href={jobStatus.download_url} download>下載譯文</a>}
                <Button variant="secondary" onClick={() => dispatch({ type: 'RESET' })}>開始新翻譯</Button>
              </>
            )}
            {jobStatus?.status === 'failed' && <Button variant="secondary" onClick={() => dispatch({ type: 'RESET' })}>重新開始</Button>}
          </div>
        </div>
      )}
    </div>
  );
}
