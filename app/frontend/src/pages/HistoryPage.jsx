import React from 'react';
import { Link } from 'react-router-dom';
import { useLocalStorage } from '../hooks/useLocalStorage.js';
import { Card, CardBody } from '../components/ui/Card.jsx';

function formatDate(ts) {
  return new Date(ts).toLocaleString('zh-TW');
}

export default function HistoryPage() {
  const [history] = useLocalStorage('translationHistory', []);

  if (!history.length) {
    return (
      <div className="page-center">
        <p className="text-muted">尚無翻譯紀錄</p>
        <Link to="/" className="btn btn-primary">開始翻譯</Link>
      </div>
    );
  }

  return (
    <div className="history-page">
      <div className="page-header"><h2 className="page-title">翻譯歷史</h2></div>
      <div className="history-list">
        {history.map((entry, i) => (
          <Card key={i}>
            <CardBody>
              <div className="history-item">
                <div>
                  <p className="history-job-id">{entry.jobId?.slice(0, 8)}...</p>
                  <p className="text-muted">{formatDate(entry.completedAt)}</p>
                </div>
                <div>
                  <p>{entry.fileCount} 個檔案</p>
                  <p>{entry.targets?.join(', ')}</p>
                </div>
                <div>
                  <span className={`badge badge-${entry.status === 'completed' ? 'success' : 'danger'}`}>
                    {entry.status === 'completed' ? '完成' : '失敗'}
                  </span>
                  {entry.duration && <p>{entry.duration.toFixed(1)}s</p>}
                </div>
              </div>
            </CardBody>
          </Card>
        ))}
      </div>
    </div>
  );
}
