import React, { useReducer, useState, useEffect } from 'react';
import { toast } from 'sonner';
import { StepWizard } from '../components/domain/StepWizard.jsx';
import { FileDropZone } from '../components/domain/FileDropZone.jsx';
import { FileCard } from '../components/domain/FileCard.jsx';
import { LanguageGrid } from '../components/domain/LanguageGrid.jsx';
import { TranscriptViewer } from '../components/domain/TranscriptViewer.jsx';
import { Button } from '../components/ui/Button.jsx';
import { Select } from '../components/ui/Select.jsx';
import { useJobPolling } from '../hooks/useJobPolling.js';
import { createMediaJob, cancelMediaJob, fetchMediaJobStatus, fetchTranscript, mediaDownloadUrl } from '../api/media.js';
import { getProviderLiveModels } from '../api/system.js';
import { ACCEPTED_MEDIA_EXTENSIONS } from '../constants/mediaFileTypes.js';

const STEPS = [
  { id: 'upload', label: '上傳' },
  { id: 'settings', label: '設定' },
  { id: 'progress', label: '進度/結果' },
];

// stage order the backend pipeline emits via MediaJobStatus.stage (media_job_manager.py);
// VAD runs before denoise so denoising can chunk by VAD's pause boundaries.
// "denoising" only appears when denoise was enabled at submission time.
const STAGE_LABELS = {
  extracting: '擷取音訊',
  vad_segmenting: '語音分段',
  denoising: '降噪處理',
  transcribing: '語音辨識',
  translating: '翻譯中',
  rendering: '產出逐字稿',
};
const VIDEO_EXTENSIONS = ['.mp4', '.mov', '.mkv', '.webm'];

const initialState = {
  step: 1,
  file: null,
  selectedTargets: [],
  providerOverride: 'auto',
  modelOverride: null,
  denoise: true,
  jobId: null,
  jobStatus: null,
  transcript: null,
  loading: false,
};

const ACTIVE_JOB_KEY = 'mediaActiveJobId';

function makeInitialState() {
  let jobId = null;
  try { jobId = localStorage.getItem(ACTIVE_JOB_KEY) || null; } catch {}
  const step = jobId ? 3 : 1;
  return { ...initialState, jobId, step };
}

function reducer(state, action) {
  switch (action.type) {
    case 'SET_FILE': return { ...state, file: action.payload };
    case 'REMOVE_FILE': return { ...state, file: null };
    case 'SET_TARGETS': return { ...state, selectedTargets: action.payload };
    case 'SET_PROVIDER': return { ...state, providerOverride: action.payload, modelOverride: null };
    case 'SET_MODEL': return { ...state, modelOverride: action.payload };
    case 'SET_DENOISE': return { ...state, denoise: action.payload };
    case 'SET_STEP': return { ...state, step: action.payload };
    case 'SET_JOB_ID': {
      try { if (action.payload) localStorage.setItem(ACTIVE_JOB_KEY, action.payload); } catch {}
      return { ...state, jobId: action.payload };
    }
    case 'SET_JOB_STATUS': return { ...state, jobStatus: action.payload };
    case 'SET_TRANSCRIPT': return { ...state, transcript: action.payload };
    case 'SET_LOADING': return { ...state, loading: action.payload };
    case 'RESET': {
      try { localStorage.removeItem(ACTIVE_JOB_KEY); } catch {}
      return { ...initialState };
    }
    default: return state;
  }
}

function StageStep({ label, done, active }) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--space-2)',
        padding: 'var(--space-1) var(--space-3)',
        borderRadius: 'var(--radius-full)',
        fontSize: 'var(--text-sm)',
        fontWeight: active ? 700 : 500,
        color: active ? 'var(--text-inverse)' : done ? 'var(--success-dark)' : 'var(--text-muted)',
        background: active ? 'var(--primary)' : done ? 'var(--success-light)' : 'var(--bg-secondary)',
        border: active || done ? 'none' : '1px solid var(--border-light)',
      }}
    >
      {label}
    </div>
  );
}

export default function MediaTranslatePage() {
  const [state, dispatch] = useReducer(reducer, null, makeInitialState);
  const [liveModels, setLiveModels] = useState([]);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [mediaUrl, setMediaUrl] = useState(null);

  const { step, file, selectedTargets, providerOverride, modelOverride, denoise, jobId, jobStatus, transcript, loading } = state;
  const isProcessing = jobStatus && !['completed', 'failed', 'cancelled'].includes(jobStatus.status);

  const deepseekKey = (() => { try { return localStorage.getItem('deepseek_api_key') || ''; } catch { return ''; } })();

  // Local object URL for playback in TranscriptViewer — only available for the
  // duration of this session (there is no backend endpoint to re-serve the
  // source media after a page reload, so it gracefully stays null then).
  useEffect(() => {
    if (!file) { setMediaUrl(null); return; }
    const url = URL.createObjectURL(file);
    setMediaUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  // Fetch live models when provider selector changes (copied wiring from TranslatePage.jsx)
  useEffect(() => {
    if (providerOverride === 'auto') {
      setLiveModels([]);
      return;
    }
    setModelsLoading(true);
    getProviderLiveModels(providerOverride, providerOverride === 'deepseek' ? deepseekKey : null)
      .then(models => {
        setLiveModels(models);
        dispatch({ type: 'SET_MODEL', payload: models[0] || null });
      })
      .catch(() => setLiveModels([]))
      .finally(() => setModelsLoading(false));
  }, [providerOverride]); // eslint-disable-line react-hooks/exhaustive-deps

  function handleJobUpdate(data) {
    dispatch({ type: 'SET_JOB_STATUS', payload: data });
    if (data.status === 'completed') {
      toast.success('轉錄與翻譯完成');
    } else if (data.status === 'failed') {
      toast.error(data.error || '處理失敗', { duration: Infinity });
    }
  }

  useJobPolling(jobId, handleJobUpdate, () => dispatch({ type: 'RESET' }), 2000, fetchMediaJobStatus);

  // Fetch the transcript once the job completes
  useEffect(() => {
    if (jobStatus?.status === 'completed' && jobId && !transcript) {
      fetchTranscript(jobId)
        .then(data => dispatch({ type: 'SET_TRANSCRIPT', payload: data }))
        .catch(err => toast.error(err.message));
    }
  }, [jobId, jobStatus?.status]); // eslint-disable-line react-hooks/exhaustive-deps

  function handleFilesAdded(newFiles) {
    if (newFiles.length > 1) toast.info('影音翻譯僅支援單一檔案，已取用第一個檔案');
    dispatch({ type: 'SET_FILE', payload: newFiles[0] });
  }

  async function handleSubmit() {
    dispatch({ type: 'SET_LOADING', payload: true });
    try {
      const form = new FormData();
      form.append('file', file);
      form.append('targets', selectedTargets.join(','));
      form.append('denoise', String(denoise));
      if (providerOverride && providerOverride !== 'auto') {
        form.append('provider_override', providerOverride);
        if (modelOverride) form.append('model_override', modelOverride);
      }
      const data = await createMediaJob(form);
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
      await cancelMediaJob(jobId);
      toast.info('已要求取消');
    } catch (err) {
      toast.error(err.message);
    }
  }

  function handleStepClick(s) {
    if (isProcessing) {
      toast.warning('處理進行中，請等待完成或取消後再切換');
      return;
    }
    dispatch({ type: 'SET_STEP', payload: s });
  }

  const providerOptions = [
    { value: 'auto', label: '自動（依語言路由）' },
    { value: 'panjit', label: 'PANJIT API' },
    ...(deepseekKey ? [{ value: 'deepseek', label: 'DeepSeek' }] : []),
  ];
  const modelOptions = modelsLoading
    ? [{ value: '', label: '載入中...' }]
    : liveModels.map(m => ({ value: m, label: m }));

  const stageOrder = Object.keys(STAGE_LABELS).filter(s => denoise || s !== 'denoising');
  const stageIndex = jobStatus ? stageOrder.indexOf(jobStatus.stage) : -1;
  const mediaKind = file && VIDEO_EXTENSIONS.some(ext => file.name.toLowerCase().endsWith(ext)) ? 'video' : 'audio';

  return (
    <div className="translate-page">
      <StepWizard steps={STEPS} currentStep={step} onStepClick={handleStepClick} locked={isProcessing} />

      {step === 1 && (
        <div className="step-content">
          <FileDropZone acceptedExtensions={ACCEPTED_MEDIA_EXTENSIONS} onFilesAdded={handleFilesAdded} />
          {file && (
            <div className="file-list">
              <FileCard file={file} onRemove={() => dispatch({ type: 'REMOVE_FILE' })} />
            </div>
          )}
          <div className="step-actions">
            <Button disabled={!file} onClick={() => dispatch({ type: 'SET_STEP', payload: 2 })}>下一步</Button>
          </div>
        </div>
      )}

      {step === 2 && (
        <div className="step-content step-2-layout">
          <div className="step-2-left">
            <h3>目標語言</h3>
            <LanguageGrid selected={selectedTargets} onChange={targets => dispatch({ type: 'SET_TARGETS', payload: targets })} />
          </div>
          <div className="step-2-right">
            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
              來源語言將逐段自動偵測，適合多語會議。
            </p>
            <Select
              label="翻譯端點"
              options={providerOptions}
              value={providerOverride}
              onChange={e => dispatch({ type: 'SET_PROVIDER', payload: e.target.value })}
            />
            {providerOverride !== 'auto' && (
              <Select
                label="模型"
                options={modelOptions}
                value={modelOverride || ''}
                onChange={e => dispatch({ type: 'SET_MODEL', payload: e.target.value })}
              />
            )}
            <label style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', cursor: 'pointer', marginTop: 'var(--space-3)' }}>
              <input
                type="checkbox"
                checked={denoise}
                onChange={e => dispatch({ type: 'SET_DENOISE', payload: e.target.checked })}
                style={{ width: 16, height: 16, cursor: 'pointer' }}
              />
              啟用降噪前處理
            </label>
          </div>
          <div className="step-actions">
            <Button variant="secondary" onClick={() => dispatch({ type: 'SET_STEP', payload: 1 })}>上一步</Button>
            <Button disabled={selectedTargets.length === 0 || loading} onClick={handleSubmit}>
              {loading ? '提交中...' : '開始處理'}
            </Button>
          </div>
        </div>
      )}

      {step === 3 && (
        <div className="step-content">
          {jobStatus && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-2)', marginBottom: 'var(--space-4)' }}>
              {jobStatus.status === 'failed' ? (
                <StageStep label="失敗" active done={false} />
              ) : jobStatus.status === 'cancelled' ? (
                <StageStep label="已取消" active done={false} />
              ) : (
                stageOrder.map((s, i) => (
                  <StageStep key={s} label={STAGE_LABELS[s]} active={i === stageIndex} done={stageIndex > i || jobStatus.status === 'completed'} />
                ))
              )}
            </div>
          )}
          {jobStatus?.status === 'failed' && jobStatus.error && (
            <p style={{ color: 'var(--error)', fontSize: 'var(--text-sm)' }}>{jobStatus.error}</p>
          )}

          {jobStatus?.status === 'completed' && transcript && (
            <>
              <TranscriptViewer transcript={transcript} mediaUrl={mediaUrl} mediaKind={mediaKind} />
              <div className="step-actions">
                <a className="btn btn-primary" href={mediaDownloadUrl(jobId)} download>下載逐字稿（.txt）</a>
              </div>
            </>
          )}

          <div className="step-actions">
            {isProcessing && <Button variant="danger" onClick={handleCancel}>取消處理</Button>}
            {jobStatus?.status === 'completed' && (
              <Button variant="secondary" onClick={() => dispatch({ type: 'RESET' })}>開始新的處理</Button>
            )}
            {(jobStatus?.status === 'failed' || jobStatus?.status === 'cancelled') && (
              <Button variant="secondary" onClick={() => dispatch({ type: 'RESET' })}>重新開始</Button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
