import React from 'react';

export function TranslationProgress({ status }) {
  if (!status) return null;
  const { overall_progress = 0, files = [], stats = {} } = status;

  return (
    <div className="translation-progress">
      <div className="progress-bar-wrapper">
        <div className="progress-bar" style={{ width: `${overall_progress}%` }} />
      </div>
      <p>{Math.round(overall_progress)}% 完成</p>
      {stats.speed && <p>速度: {stats.speed} seg/min</p>}
      {stats.eta && <p>預計剩餘: {stats.eta}</p>}
      {files.map(f => (
        <div key={f.name} className="file-progress">
          <span>{f.name}</span>
          <div className="progress-bar-wrapper">
            <div className="progress-bar" style={{ width: `${f.progress ?? 0}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}
