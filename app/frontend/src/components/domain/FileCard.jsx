import React from 'react';
import { FileText, X } from 'lucide-react';

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function FileCard({ file, onRemove }) {
  return (
    <div className="file-card">
      <FileText size={18} />
      <div className="file-card-info">
        <span className="file-card-name">{file.name}</span>
        <span className="file-card-size">{formatSize(file.size)}</span>
      </div>
      {onRemove && <button className="file-card-remove" onClick={onRemove}><X size={14} /></button>}
    </div>
  );
}
