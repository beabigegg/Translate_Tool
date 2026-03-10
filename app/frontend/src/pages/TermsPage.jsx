import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import { Tabs } from '../components/ui/Tabs.jsx';
import { Card, CardBody } from '../components/ui/Card.jsx';
import { Button } from '../components/ui/Button.jsx';
import { Spinner } from '../components/feedback/Spinner.jsx';
import { fetchTermStats, getTermExportUrl, fetchApprovedTerms, importTerms } from '../api/terms.js';

export default function TermsPage() {
  const [activeTab, setActiveTab] = useState('overview');
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [exportFormat, setExportFormat] = useState('json');
  const [importStrategy, setImportStrategy] = useState('skip');

  useEffect(() => {
    fetchTermStats()
      .then(s => setStats(s))
      .catch(err => toast.error(`載入統計失敗: ${err.message}`))
      .finally(() => setLoading(false));
  }, []);

  async function handleImport(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const result = await importTerms(file, importStrategy);
      toast.success(`匯入完成：新增 ${result.added ?? 0} 筆、略過 ${result.skipped ?? 0} 筆、覆蓋 ${result.overwritten ?? 0} 筆`);
      const s = await fetchTermStats();
      setStats(s);
    } catch (err) {
      toast.error(`匯入失敗: ${err.message}`);
    }
  }

  const tabs = [
    { id: 'overview', label: '總覽' },
    { id: 'approved', label: '已核准' },
    { id: 'import-export', label: '匯入匯出' },
  ];

  if (loading) return <div className="page-center"><Spinner /></div>;

  return (
    <div className="terms-page">
      <div className="page-header">
        <h2 className="page-title">術語庫</h2>
        <Link to="/terms/review" className="btn btn-primary">審核待審術語 {stats?.pending_count ? `(${stats.pending_count})` : ''}</Link>
      </div>

      <Tabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab} />

      {activeTab === 'overview' && (
        <div className="stats-grid">
          <Card><CardBody><div className="stat-card"><p className="stat-label">總術語數</p><p className="stat-value">{stats?.total_count ?? 0}</p></div></CardBody></Card>
          <Card><CardBody><div className="stat-card"><p className="stat-label">待審核</p><p className="stat-value">{stats?.pending_count ?? 0}</p></div></CardBody></Card>
          <Card><CardBody><div className="stat-card"><p className="stat-label">已核准</p><p className="stat-value">{stats?.approved_count ?? 0}</p></div></CardBody></Card>
        </div>
      )}

      {activeTab === 'approved' && (
        <ApprovedTermsTab />
      )}

      {activeTab === 'import-export' && (
        <div className="import-export-section">
          <Card>
            <CardBody>
              <h3>匯出術語庫</h3>
              <div className="form-group">
                <label className="form-label">格式</label>
                <select className="form-select" value={exportFormat} onChange={e => setExportFormat(e.target.value)}>
                  <option value="json">JSON</option>
                  <option value="csv">CSV</option>
                  <option value="xlsx">XLSX</option>
                </select>
              </div>
              <a className="btn btn-primary" href={getTermExportUrl(exportFormat)} download>匯出</a>
            </CardBody>
          </Card>
          <Card>
            <CardBody>
              <h3>匯入術語庫</h3>
              <div className="form-group">
                <label className="form-label">衝突策略</label>
                <select className="form-select" value={importStrategy} onChange={e => setImportStrategy(e.target.value)}>
                  <option value="skip">保留現有 (skip)</option>
                  <option value="overwrite">覆蓋 (overwrite)</option>
                  <option value="merge">依信心值合併 (merge)</option>
                </select>
              </div>
              <label className="btn btn-secondary">選擇檔案<input type="file" style={{ display: 'none' }} onChange={handleImport} /></label>
            </CardBody>
          </Card>
        </div>
      )}
    </div>
  );
}

function ApprovedTermsTab() {
  const [terms, setTerms] = useState([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    fetchApprovedTerms().then(setTerms).catch(err => toast.error(err.message)).finally(() => setLoading(false));
  }, []);
  if (loading) return <Spinner />;
  if (!terms.length) return <p className="text-muted">尚無已核准術語</p>;
  return (
    <div className="term-list">
      {terms.map((t, i) => (
        <div key={i} className="term-item">
          <span className="term-source">{t.source_text}</span>
          <span className="term-arrow">→</span>
          <span className="term-target">{t.target_text}</span>
          <span className="term-meta">{t.target_lang} · {t.domain}</span>
        </div>
      ))}
    </div>
  );
}
