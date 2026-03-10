import React, { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Card, CardBody } from '../components/ui/Card.jsx';
import { Button } from '../components/ui/Button.jsx';
import { VramCalculator } from '../components/domain/VramCalculator.jsx';
import { useSettings } from '../contexts/SettingsContext.jsx';
import { useTheme } from '../hooks/useTheme.js';
import { fetchHealth, fetchCacheStats, clearCache } from '../api/system.js';

export default function SettingsPage() {
  const { state, dispatch } = useSettings();
  const { theme, setTheme } = useTheme();
  const [health, setHealth] = useState(null);
  const [cacheStats, setCacheStats] = useState(null);

  useEffect(() => {
    fetchHealth().then(setHealth).catch(() => {});
    fetchCacheStats().then(setCacheStats).catch(() => {});
  }, []);

  async function handleClearCache() {
    try {
      await clearCache();
      toast.success('快取已清除');
      setCacheStats(null);
    } catch (err) {
      toast.error(err.message);
    }
  }

  return (
    <div className="settings-page">
      <Card>
        <CardBody>
          <h3 className="section-title">系統狀態</h3>
          {health ? (
            <div className="health-info">
              <p>Ollama 狀態: <strong>{health.status}</strong></p>
              {health.version && <p>版本: {health.version}</p>}
            </div>
          ) : <p className="text-muted">無法連線至 Ollama</p>}
          {cacheStats && (
            <div className="cache-info">
              <p>快取項目: {cacheStats.count ?? 'N/A'}</p>
              <Button variant="secondary" onClick={handleClearCache}>清除快取</Button>
            </div>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardBody>
          <h3 className="section-title">GPU 與記憶體</h3>
          <VramCalculator />
        </CardBody>
      </Card>

      <Card>
        <CardBody>
          <h3 className="section-title">翻譯預設值</h3>
          <div className="form-group">
            <label className="form-label">預設來源語言</label>
            <select className="form-select" value={state.defaultSrcLang} onChange={e => { dispatch({ type: 'SET_DEFAULT_SRC_LANG', payload: e.target.value }); localStorage.setItem('defaultSrcLang', JSON.stringify(e.target.value)); }}>
              <option value="auto">自動偵測</option>
              <option value="Traditional Chinese">Traditional Chinese</option>
              <option value="English">English</option>
            </select>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardBody>
          <h3 className="section-title">介面</h3>
          <div className="form-group">
            <label className="form-label">主題</label>
            <div className="theme-toggle">
              {[['light', '淺色'], ['dark', '暗色'], ['system', '跟隨系統']].map(([val, label]) => (
                <button key={val} className={`theme-btn ${theme === val ? 'theme-btn-active' : ''}`} onClick={() => setTheme(val)}>{label}</button>
              ))}
            </div>
          </div>
          <div className="form-group">
            <label className="form-label">語言</label>
            <select className="form-select" value={state.uiLanguage} onChange={e => dispatch({ type: 'SET_LANGUAGE', payload: e.target.value })}>
              <option value="zh-TW">繁體中文</option>
              <option value="en">English</option>
            </select>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
