import React, { useEffect, useState, useRef } from 'react';
import { toast } from 'sonner';
import { Card, CardBody } from '../components/ui/Card.jsx';
import { Button } from '../components/ui/Button.jsx';
import { useSettings } from '../contexts/SettingsContext.jsx';
import { useTheme } from '../hooks/useTheme.js';
import { useHealthCheck } from '../hooks/useHealthCheck.js';
import { getProviderModels, testTranslation } from '../api/system.js';
import { useTranslation } from '../i18n/index.js';

const SRC_LANG_OPTIONS = [
  { value: 'zh-TW', label: '繁體中文 (zh-TW)' },
  { value: 'en', label: 'English (en)' },
  { value: 'ja', label: '日本語 (ja)' },
  { value: 'ko', label: '한국어 (ko)' },
  { value: 'de', label: 'Deutsch (de)' },
  { value: 'fr', label: 'Français (fr)' },
];

const TARGET_OPTIONS = [
  { value: 'en', label: 'English' },
  { value: 'zh-TW', label: '繁體中文' },
  { value: 'ja', label: '日本語' },
  { value: 'ko', label: '한국어' },
  { value: 'de', label: 'Deutsch' },
  { value: 'fr', label: 'Français' },
];

// --- Provider Status Badge ---
function ProviderStatusBadge({ status, latencyMs, labels = {} }) {
  const { online = 'Online', offline = 'Offline', notConfigured = 'Not configured' } = labels;
  const dotStyle = {
    display: 'inline-block',
    width: '0.625rem',
    height: '0.625rem',
    borderRadius: 'var(--radius-full)',
    marginRight: 'var(--space-2)',
    flexShrink: 0,
  };

  if (status === 'online') {
    return (
      <span style={{ display: 'inline-flex', alignItems: 'center', color: 'var(--success)' }}>
        <span style={{ ...dotStyle, background: 'var(--success)' }} aria-hidden="true" />
        {online}{latencyMs != null ? ` (${Math.round(latencyMs)} ms)` : ''}
      </span>
    );
  }
  if (status === 'offline') {
    return (
      <span style={{ display: 'inline-flex', alignItems: 'center', color: 'var(--error)' }}>
        <span style={{ ...dotStyle, background: 'var(--error)' }} aria-hidden="true" />
        {offline}
      </span>
    );
  }
  // not_configured or unknown
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', color: 'var(--text-muted)' }}>
      <span style={{ ...dotStyle, background: 'var(--text-muted)' }} aria-hidden="true" />
      {notConfigured}
    </span>
  );
}

// --- Test result card ---
function ResultCard({ result }) {
  const isError = Boolean(result.error);
  const borderColor = isError ? 'var(--error)' : 'var(--success)';
  return (
    <div
      className="result-card"
      style={{
        border: `1px solid ${borderColor}`,
        borderRadius: 'var(--radius-lg)',
        padding: 'var(--space-4)',
        marginBottom: 'var(--space-3)',
        background: 'var(--bg-secondary)',
      }}
      role="region"
      aria-label={`Result for ${result.model_id}`}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 'var(--space-2)' }}>
        <strong style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
          {result.provider} / {result.model_id}
        </strong>
        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
          {result.duration_ms != null ? `${Math.round(result.duration_ms)} ms` : null}
        </span>
      </div>
      {isError ? (
        <p style={{ color: 'var(--error)', fontSize: 'var(--text-sm)', margin: 0 }}>
          {result.error}
        </p>
      ) : (
        <>
          <p style={{ margin: '0 0 var(--space-2)', fontSize: 'var(--text-sm)' }}>
            {result.translation}
          </p>
          {result.comet_score != null && (
            <p style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', margin: 0 }}>
              COMET: {result.comet_score.toFixed(3)}
            </p>
          )}
        </>
      )}
    </div>
  );
}

export default function SettingsPage() {
  const { state, dispatch } = useSettings();
  const { theme, setTheme } = useTheme();
  const { t } = useTranslation();
  const { providerHealth, providerHealthLoading, checkProviders } = useHealthCheck();

  // --- Provider models ---
  const [providerModels, setProviderModels] = useState([]);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [modelsError, setModelsError] = useState(null);

  // --- DeepSeek API key (localStorage-only) ---
  const [deepseekKey, setDeepseekKey] = useState(() => localStorage.getItem('deepseek_api_key') || '');
  const [keyDraft, setKeyDraft] = useState(() => localStorage.getItem('deepseek_api_key') || '');
  const hasDeepseekKey = deepseekKey.trim().length > 0;

  // --- Test Translation ---
  const [testText, setTestText] = useState('');
  const [testSrcLang, setTestSrcLang] = useState('zh-TW');
  const [testTargets, setTestTargets] = useState(['en']);
  const [testModels, setTestModels] = useState(['panjit']);
  const [testRunning, setTestRunning] = useState(false);
  const [testResults, setTestResults] = useState([]);

  // On mount: load provider models and run health check
  useEffect(() => {
    setModelsLoading(true);
    getProviderModels()
      .then(data => { setProviderModels(Array.isArray(data) ? data : []); setModelsError(null); })
      .catch(err => { setProviderModels([]); setModelsError(err.message || 'Failed to load model configuration'); })
      .finally(() => setModelsLoading(false));

    const storedKey = localStorage.getItem('deepseek_api_key') || '';
    checkProviders(storedKey || null);
  }, [checkProviders]);

  function handleRefreshHealth() {
    checkProviders(deepseekKey || null);
  }

  // --- DeepSeek key actions ---
  function handleSaveKey() {
    const trimmed = keyDraft.trim();
    localStorage.setItem('deepseek_api_key', trimmed);
    setDeepseekKey(trimmed);
    toast.success('DeepSeek API key saved');
    checkProviders(trimmed || null);
  }

  function handleClearKey() {
    localStorage.removeItem('deepseek_api_key');
    setDeepseekKey('');
    setKeyDraft('');
    setTestModels(prev => prev.filter(m => m !== 'deepseek'));
    toast.info('DeepSeek API key cleared');
    checkProviders(null);
  }

  // --- Test translation target toggle ---
  function toggleTarget(val) {
    setTestTargets(prev =>
      prev.includes(val) ? prev.filter(v => v !== val) : [...prev, val]
    );
  }

  function toggleModel(val) {
    setTestModels(prev =>
      prev.includes(val) ? prev.filter(v => v !== val) : [...prev, val]
    );
  }

  // Build list of available model slots from providerModels
  const availableModelSlots = providerModels.map(pm => pm.provider);

  async function handleRunTest() {
    if (!testText.trim()) {
      toast.warning(t('settings.warnNoText'));
      return;
    }
    if (testTargets.length === 0) {
      toast.warning(t('settings.warnNoTarget'));
      return;
    }
    if (testModels.length === 0) {
      toast.warning(t('settings.warnNoProvider'));
      return;
    }
    setTestRunning(true);
    setTestResults([]);
    try {
      const payload = {
        text: testText.trim(),
        src_lang: testSrcLang,
        targets: testTargets,
        models: testModels,
        deepseek_api_key: localStorage.getItem('deepseek_api_key') || null,
      };
      const results = await testTranslation(payload);
      setTestResults(Array.isArray(results) ? results : []);
    } catch (err) {
      toast.error(err.message);
    } finally {
      setTestRunning(false);
    }
  }

  // Resolve provider health entry by name (case-insensitive)
  function getHealth(provider) {
    return providerHealth.find(h => h.provider?.toLowerCase() === provider.toLowerCase()) || null;
  }

  const panjitHealth = getHealth('panjit');
  const deepseekHealth = getHealth('deepseek');

  return (
    <div className="settings-page">

      {/* Section 1: Provider Status */}
      <Card>
        <CardBody>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-4)' }}>
            <h3 className="section-title" style={{ margin: 0 }}>{t('settings.providerStatus')}</h3>
            <Button
              variant="secondary"
              size="sm"
              onClick={handleRefreshHealth}
              disabled={providerHealthLoading}
              aria-label="Refresh provider health"
            >
              {providerHealthLoading ? t('msg.loading') : t('btn.refresh')}
            </Button>
          </div>

          <table style={{ width: '100%', borderCollapse: 'collapse' }} role="table">
            <thead>
              <tr>
                <th style={{ textAlign: 'left', padding: 'var(--space-2) var(--space-3)', fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', borderBottom: '1px solid var(--border-light)' }}>
                  {t('label.provider')}
                </th>
                <th style={{ textAlign: 'left', padding: 'var(--space-2) var(--space-3)', fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', borderBottom: '1px solid var(--border-light)' }}>
                  {t('label.status')}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td style={{ padding: 'var(--space-3)', fontSize: 'var(--text-sm)', fontWeight: 500 }}>PANJIT</td>
                <td style={{ padding: 'var(--space-3)' }}>
                  {providerHealthLoading
                    ? <span style={{ color: 'var(--text-muted)', fontSize: 'var(--text-sm)' }}>{t('msg.loading')}</span>
                    : <ProviderStatusBadge
                        status={panjitHealth?.status ?? 'offline'}
                        latencyMs={panjitHealth?.latency_ms}
                        labels={{ online: t('provider.online'), offline: t('provider.offline'), notConfigured: t('provider.notConfigured') }}
                      />
                  }
                </td>
              </tr>
              <tr>
                <td style={{ padding: 'var(--space-3)', fontSize: 'var(--text-sm)', fontWeight: 500 }}>DeepSeek</td>
                <td style={{ padding: 'var(--space-3)' }}>
                  {providerHealthLoading
                    ? <span style={{ color: 'var(--text-muted)', fontSize: 'var(--text-sm)' }}>{t('msg.loading')}</span>
                    : <ProviderStatusBadge
                        status={hasDeepseekKey ? (deepseekHealth?.status ?? 'offline') : 'not_configured'}
                        latencyMs={deepseekHealth?.latency_ms}
                        labels={{ online: t('provider.online'), offline: t('provider.offline'), notConfigured: t('provider.notConfigured') }}
                      />
                  }
                </td>
              </tr>
            </tbody>
          </table>
        </CardBody>
      </Card>

      {/* Section 2: Model Configuration */}
      <Card>
        <CardBody>
          <h3 className="section-title">{t('settings.modelConfig')}</h3>
          {modelsLoading ? (
            <p className="text-muted">{t('msg.loading')}</p>
          ) : modelsError ? (
            <p style={{ color: 'var(--error)', fontSize: 'var(--text-sm)' }}>{modelsError}</p>
          ) : providerModels.length === 0 ? (
            <p className="text-muted">{t('msg.noModels')}</p>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse' }} role="table">
              <thead>
                <tr>
                  <th style={{ textAlign: 'left', padding: 'var(--space-2) var(--space-3)', fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', borderBottom: '1px solid var(--border-light)' }}>
                    {t('label.provider')}
                  </th>
                  <th style={{ textAlign: 'left', padding: 'var(--space-2) var(--space-3)', fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', borderBottom: '1px solid var(--border-light)' }}>
                    {t('label.translateModel')}
                  </th>
                  <th style={{ textAlign: 'left', padding: 'var(--space-2) var(--space-3)', fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', borderBottom: '1px solid var(--border-light)' }}>
                    {t('label.longDocModel')}
                  </th>
                </tr>
              </thead>
              <tbody>
                {providerModels.map(pm => (
                  <tr key={pm.provider}>
                    <td style={{ padding: 'var(--space-3)', fontSize: 'var(--text-sm)', fontWeight: 500 }}>
                      {pm.provider}
                    </td>
                    <td style={{ padding: 'var(--space-3)', fontSize: 'var(--text-sm)', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                      {pm.translate_model ?? <span style={{ color: 'var(--text-muted)' }}>—</span>}
                    </td>
                    <td style={{ padding: 'var(--space-3)', fontSize: 'var(--text-sm)', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                      {pm.long_doc_model ?? <span style={{ color: 'var(--text-muted)' }}>—</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardBody>
      </Card>

      {/* Section 3: DeepSeek API Key */}
      <Card>
        <CardBody>
          <h3 className="section-title">{t('settings.deepseekKey')}</h3>
          <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', marginBottom: 'var(--space-4)' }}>
            {t('settings.deepseekKeyDesc')}
          </p>
          <div style={{ marginBottom: 'var(--space-2)' }}>
            <span style={{
              display: 'inline-block',
              fontSize: 'var(--text-xs)',
              fontWeight: 600,
              padding: '0.125rem var(--space-2)',
              borderRadius: 'var(--radius-sm)',
              background: hasDeepseekKey ? 'var(--success-light)' : 'var(--neutral-100)',
              color: hasDeepseekKey ? 'var(--success-dark)' : 'var(--text-muted)',
              marginBottom: 'var(--space-3)',
            }}>
              {hasDeepseekKey ? t('settings.keyConfigured') : t('settings.keyNotConfigured')}
            </span>
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="deepseek-key-input">
              {t('settings.deepseekKey')}
            </label>
            <input
              id="deepseek-key-input"
              type="password"
              className="form-input"
              value={keyDraft}
              onChange={e => setKeyDraft(e.target.value)}
              placeholder={t('settings.deepseekKeyPlaceholder')}
              autoComplete="off"
              style={{ width: '100%', marginBottom: 'var(--space-3)' }}
            />
          </div>
          <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
            <Button onClick={handleSaveKey} disabled={keyDraft === deepseekKey}>
              {t('btn.save')}
            </Button>
            <Button variant="secondary" onClick={handleClearKey} disabled={!hasDeepseekKey && !keyDraft}>
              {t('btn.clear')}
            </Button>
          </div>
        </CardBody>
      </Card>

      {/* Section 4: Test Translation */}
      <Card>
        <CardBody>
          <h3 className="section-title">{t('settings.testTranslation')}</h3>

          <div className="form-group">
            <label className="form-label" htmlFor="test-text-input">
              {t('label.sourceText')}
            </label>
            <textarea
              id="test-text-input"
              className="form-input"
              rows={3}
              value={testText}
              onChange={e => setTestText(e.target.value)}
              placeholder={t('settings.testTextPlaceholder')}
              style={{ width: '100%', resize: 'vertical' }}
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-4)', marginBottom: 'var(--space-4)' }}>
            <div className="form-group">
              <label className="form-label" htmlFor="test-src-lang">
                {t('label.srcLang')}
              </label>
              <select
                id="test-src-lang"
                className="form-select"
                value={testSrcLang}
                onChange={e => setTestSrcLang(e.target.value)}
              >
                {SRC_LANG_OPTIONS.map(o => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">{t('label.targetLangs')}</label>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-2)' }}>
                {TARGET_OPTIONS.map(o => (
                  <label
                    key={o.value}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 'var(--space-1)',
                      fontSize: 'var(--text-sm)',
                      cursor: 'pointer',
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={testTargets.includes(o.value)}
                      onChange={() => toggleTarget(o.value)}
                    />
                    {o.label}
                  </label>
                ))}
              </div>
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">{t('label.providers')}</label>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-3)' }}>
              {/* PANJIT is always available */}
              <label
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 'var(--space-1)',
                  fontSize: 'var(--text-sm)',
                  cursor: 'pointer',
                }}
              >
                <input
                  type="checkbox"
                  value="panjit"
                  checked={testModels.includes('panjit')}
                  onChange={() => toggleModel('panjit')}
                />
                PANJIT
              </label>
              {/* DeepSeek only when key is configured */}
              <label
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 'var(--space-1)',
                  fontSize: 'var(--text-sm)',
                  cursor: hasDeepseekKey ? 'pointer' : 'not-allowed',
                  opacity: hasDeepseekKey ? 1 : 0.5,
                }}
                title={hasDeepseekKey ? undefined : t('settings.deepseekKeyRequired')}
              >
                <input
                  type="checkbox"
                  value="deepseek"
                  checked={testModels.includes('deepseek')}
                  onChange={() => hasDeepseekKey && toggleModel('deepseek')}
                  disabled={!hasDeepseekKey}
                />
                DeepSeek
              </label>
            </div>
          </div>

          <div style={{ marginTop: 'var(--space-4)' }}>
            <Button
              onClick={handleRunTest}
              disabled={
                testRunning ||
                !testText.trim() ||
                testTargets.length === 0 ||
                testModels.length === 0 ||
                (testModels.length === 1 && testModels[0] === 'deepseek' && !hasDeepseekKey)
              }
            >
              {testRunning ? t('settings.testRunning') : t('settings.runTest')}
            </Button>
          </div>

          {testResults.length > 0 && (
            <div style={{ marginTop: 'var(--space-6)' }} role="region" aria-label="Test results">
              <h4 style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', marginBottom: 'var(--space-3)' }}>
                {t('settings.testResults')}
              </h4>
              {testResults.map((r, i) => (
                <ResultCard key={`${r.model_id}-${i}`} result={r} />
              ))}
            </div>
          )}
        </CardBody>
      </Card>

      {/* Existing: Translation Defaults */}
      <Card>
        <CardBody>
          <h3 className="section-title">{t('settings.defaults')}</h3>
          <div className="form-group">
            <label className="form-label">{t('label.srcLang')}</label>
            <select
              className="form-select"
              value={state.defaultSrcLang}
              onChange={e => {
                dispatch({ type: 'SET_DEFAULT_SRC_LANG', payload: e.target.value });
                localStorage.setItem('defaultSrcLang', JSON.stringify(e.target.value));
              }}
            >
              <option value="auto">{t('label.autoDetect')}</option>
              <option value="Traditional Chinese">Traditional Chinese</option>
              <option value="English">English</option>
            </select>
          </div>
        </CardBody>
      </Card>

      {/* Existing: Interface */}
      <Card>
        <CardBody>
          <h3 className="section-title">{t('settings.interface')}</h3>
          <div className="form-group">
            <label className="form-label">{t('label.theme')}</label>
            <div className="theme-toggle">
              {[
                ['light', t('settings.themeLight')],
                ['dark', t('settings.themeDark')],
                ['system', t('settings.themeSystem')],
              ].map(([val, label]) => (
                <button
                  key={val}
                  className={`theme-btn ${theme === val ? 'theme-btn-active' : ''}`}
                  onClick={() => setTheme(val)}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
          <div className="form-group">
            <label className="form-label">{t('label.language')}</label>
            <select
              className="form-select"
              value={state.uiLanguage}
              onChange={e => dispatch({ type: 'SET_LANGUAGE', payload: e.target.value })}
            >
              <option value="zh-TW">繁體中文</option>
              <option value="en">English</option>
            </select>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
