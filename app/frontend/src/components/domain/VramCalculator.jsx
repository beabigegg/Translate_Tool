import React from 'react';
import { useSettings } from '../../contexts/SettingsContext.jsx';

export function VramCalculator({ profile }) {
  const { state, dispatch } = useSettings();
  const modelConfig = state.modelConfig;

  const cfg = modelConfig.find(c => c.model_type === (profile?.model_type ?? 'general')) || modelConfig[0];
  if (!cfg) return null;

  const numCtx = state.numCtx ?? cfg.default_num_ctx;
  const modelGb = cfg.model_size_gb;
  const kvGb = (numCtx / 1024) * cfg.kv_per_1k_ctx_gb;
  const totalGb = modelGb + kvGb;
  const pct = (totalGb / state.gpuVram) * 100;
  const barColor = pct > 90 ? 'var(--error)' : pct > 75 ? 'var(--warning)' : 'var(--success)';

  return (
    <div className="vram-calculator">
      <div className="form-group">
        <label className="form-label">GPU 顯存容量</label>
        <select className="form-select" value={state.gpuVram} onChange={e => dispatch({ type: 'SET_GPU_VRAM', payload: Number(e.target.value) })}>
          {[6, 8, 10, 12, 16, 24].map(v => <option key={v} value={v}>{v} GB</option>)}
        </select>
      </div>
      <div className="form-group">
        <label className="form-label">num_ctx: {numCtx}</label>
        <input type="range" min={cfg.min_num_ctx} max={cfg.max_num_ctx} step={512} value={numCtx}
          onChange={e => dispatch({ type: 'SET_NUM_CTX', payload: Number(e.target.value) })} />
      </div>
      <div className="vram-bar-wrapper">
        <div className="vram-bar" style={{ width: `${Math.min(pct, 100)}%`, background: barColor }} />
      </div>
      <p className="vram-breakdown">模型: {modelGb.toFixed(1)} GB + KV Cache: {kvGb.toFixed(2)} GB = 總計: {totalGb.toFixed(2)} GB / {state.gpuVram} GB</p>
    </div>
  );
}
