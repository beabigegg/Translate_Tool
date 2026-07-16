import React, { useRef, useState } from 'react';
import { Upload } from 'lucide-react';
import { ACCEPTED_EXTENSIONS } from '../../constants/fileTypes.js';

export function FileDropZone({ onFilesAdded, acceptedExtensions = ACCEPTED_EXTENSIONS }) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef(null);

  function handleFiles(files) {
    const valid = Array.from(files).filter(f =>
      acceptedExtensions.some(ext => f.name.toLowerCase().endsWith(ext))
    );
    if (valid.length > 0) onFilesAdded(valid);
  }

  return (
    <div
      className={`dropzone ${dragging ? 'dropzone-active' : ''}`}
      onDragOver={e => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={e => { e.preventDefault(); setDragging(false); handleFiles(e.dataTransfer.files); }}
      onClick={() => inputRef.current?.click()}
    >
      <Upload size={32} />
      <p>拖曳檔案至此，或點擊選擇</p>
      <p className="text-muted">支援: {acceptedExtensions.join(', ')}</p>
      <input ref={inputRef} type="file" multiple accept={acceptedExtensions.join(',')} style={{ display: 'none' }} onChange={e => handleFiles(e.target.files)} data-testid="file-upload-input" />
    </div>
  );
}
