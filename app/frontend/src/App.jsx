import React, { useEffect, useMemo, useState, useRef, useCallback } from "react";
import {
  cancelJob,
  createJob,
  fetchJobStatus,
  streamLogs
} from "./api.js";

// Language options grouped by region for better UX
const LANG_GROUPS = {
  "East Asian": ["English", "Traditional Chinese", "Simplified Chinese", "Japanese", "Korean"],
  "Southeast Asian": ["Vietnamese", "Thai", "Indonesian", "Malay", "Filipino", "Burmese", "Khmer", "Lao"],
  "South Asian": ["Hindi", "Bengali", "Tamil", "Telugu", "Marathi", "Gujarati", "Kannada", "Malayalam", "Punjabi", "Urdu", "Nepali", "Sinhala"],
  "Western European": ["French", "German", "Spanish", "Portuguese", "Italian", "Dutch"],
  "Northern European": ["Swedish", "Norwegian", "Danish", "Finnish", "Icelandic"],
  "Eastern European": ["Russian", "Polish", "Ukrainian", "Czech", "Romanian", "Hungarian", "Bulgarian", "Slovak", "Croatian", "Serbian", "Slovenian", "Lithuanian", "Latvian", "Estonian"],
  "Southern European": ["Greek", "Turkish"],
  "Middle Eastern": ["Arabic", "Hebrew", "Persian"],
  "African": ["Swahili", "Amharic", "Hausa", "Yoruba", "Zulu"]
};

// File type icons and colors
const FILE_TYPES = {
  docx: { icon: "W", color: "#2b579a", label: "Word Document" },
  pptx: { icon: "P", color: "#d24726", label: "PowerPoint" },
  xlsx: { icon: "X", color: "#217346", label: "Excel Spreadsheet" },
  pdf: { icon: "PDF", color: "#f40f02", label: "PDF Document" }
};

// Icons as reusable components
const Icons = {
  Check: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  ),
  Upload: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
      <polyline points="17 8 12 3 7 8" />
      <line x1="12" y1="3" x2="12" y2="15" />
    </svg>
  ),
  Cloud: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M7 18a4.6 4.4 0 0 1-.8-8.8A6 6 0 0 1 18 9a5 5 0 0 1 1 9.9" />
      <path d="M9 15l3-3 3 3" />
      <line x1="12" y1="12" x2="12" y2="21" />
    </svg>
  ),
  Globe: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="10" />
      <line x1="2" y1="12" x2="22" y2="12" />
      <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
    </svg>
  ),
  Star: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
    </svg>
  ),
  Settings: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  ),
  Activity: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
    </svg>
  ),
  Terminal: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="4 17 10 11 4 5" />
      <line x1="12" y1="19" x2="20" y2="19" />
    </svg>
  ),
  Translate: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12.87 15.07l-2.54-2.51.03-.03A17.52 17.52 0 0014.07 6H17V4h-7V2H8v2H1v2h11.17C11.5 7.92 10.44 9.75 9 11.35 8.07 10.32 7.3 9.19 6.69 8h-2c.73 1.63 1.73 3.17 2.98 4.56l-5.09 5.02L4 19l5-5 3.11 3.11.76-2.04z"/>
      <path d="M18.5 10h-2L12 22h2l1.12-3h4.75L21 22h2l-4.5-12zm-2.62 7l1.62-4.33L19.12 17h-3.24z"/>
    </svg>
  ),
  Play: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polygon points="5 3 19 12 5 21 5 3" />
    </svg>
  ),
  Stop: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
    </svg>
  ),
  Download: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  ),
  Refresh: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="1 4 1 10 7 10" />
      <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" />
    </svg>
  ),
  X: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  ),
  Search: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  ),
  ChevronRight: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="9 18 15 12 9 6" />
    </svg>
  ),
  ChevronDown: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="6 9 12 15 18 9" />
    </svg>
  ),
  ChevronUp: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="18 15 12 9 6 15" />
    </svg>
  ),
  Error: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="10" />
      <line x1="15" y1="9" x2="9" y2="15" />
      <line x1="9" y1="9" x2="15" y2="15" />
    </svg>
  ),
  Clock: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  ),
  FileText: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
      <polyline points="10 9 9 9 8 9" />
    </svg>
  )
};

// Step indicator component
function StepIndicator({ currentStep, steps }) {
  return (
    <div className="step-indicator">
      {steps.map((step, index) => (
        <div
          key={step.id}
          className={`step ${index < currentStep ? 'completed' : ''} ${index === currentStep ? 'active' : ''}`}
        >
          <div className="step-number">
            {index < currentStep ? <Icons.Check /> : index + 1}
          </div>
          <div className="step-content">
            <span className="step-title">{step.title}</span>
            <span className="step-desc">{step.desc}</span>
          </div>
          {index < steps.length - 1 && <div className="step-line" />}
        </div>
      ))}
    </div>
  );
}

// Progress bar component with enhanced visuals
function ProgressBar({ progress, status }) {
  return (
    <div className="progress-container">
      <div className="progress-bar">
        <div
          className={`progress-fill ${status}`}
          style={{ width: `${progress}%` }}
        />
      </div>
      <span className="progress-text">{Math.round(progress)}%</span>
    </div>
  );
}

// Status badge component with animation
function StatusBadge({ status }) {
  const statusConfig = {
    idle: { label: "Ready", className: "idle" },
    running: { label: "Translating...", className: "running" },
    completed: { label: "Completed", className: "completed" },
    failed: { label: "Failed", className: "failed" },
    cancelled: { label: "Cancelled", className: "cancelled" }
  };

  const config = statusConfig[status] || statusConfig.idle;

  return (
    <div className={`status-badge ${config.className}`}>
      <span className={`status-icon ${config.className === 'running' ? 'loader' : ''}`} />
      <span>{config.label}</span>
    </div>
  );
}

// File card component with better visual hierarchy
function FileCard({ file, onRemove }) {
  const ext = file.name.split('.').pop().toLowerCase();
  const fileType = FILE_TYPES[ext] || { icon: "?", color: "#666", label: "File" };
  const size = file.size < 1024 * 1024
    ? `${(file.size / 1024).toFixed(1)} KB`
    : `${(file.size / (1024 * 1024)).toFixed(1)} MB`;

  return (
    <div className="file-card">
      <div className="file-icon" style={{ backgroundColor: fileType.color }}>
        {fileType.icon}
      </div>
      <div className="file-info">
        <span className="file-name" title={file.name}>{file.name}</span>
        <span className="file-meta">{fileType.label} - {size}</span>
      </div>
      <button
        className="file-remove"
        onClick={onRemove}
        type="button"
        aria-label={`Remove ${file.name}`}
        title="Remove file"
      >
        <Icons.X />
      </button>
    </div>
  );
}

// Language selector with search and groups
function LanguageSelector({ selected, onChange, multiple = false, excludeAuto = false }) {
  const [search, setSearch] = useState("");
  const [expandedGroups, setExpandedGroups] = useState(new Set(["East Asian"]));

  const filteredGroups = useMemo(() => {
    if (!search) return LANG_GROUPS;
    const lower = search.toLowerCase();
    const result = {};
    Object.entries(LANG_GROUPS).forEach(([group, langs]) => {
      const filtered = langs.filter(lang => lang.toLowerCase().includes(lower));
      if (filtered.length > 0) result[group] = filtered;
    });
    return result;
  }, [search]);

  const toggleGroup = (group) => {
    setExpandedGroups(prev => {
      const next = new Set(prev);
      if (next.has(group)) next.delete(group);
      else next.add(group);
      return next;
    });
  };

  const handleSelect = (lang) => {
    onChange(lang);
  };

  const totalSelected = multiple ? selected.length : (selected ? 1 : 0);

  return (
    <div className="language-selector">
      <div className="language-search">
        <Icons.Search />
        <input
          type="text"
          placeholder="Search languages..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Search languages"
        />
        {search && (
          <button
            type="button"
            className="clear-search"
            onClick={() => setSearch("")}
            aria-label="Clear search"
          >
            <Icons.X />
          </button>
        )}
      </div>

      {!excludeAuto && !multiple && (
        <div
          className={`language-item auto ${selected === "Auto" ? "selected" : ""}`}
          onClick={() => handleSelect("Auto")}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => e.key === 'Enter' && handleSelect("Auto")}
          aria-pressed={selected === "Auto"}
        >
          <span className="auto-icon">A</span>
          <span>Auto Detect</span>
          {selected === "Auto" && <Icons.Check />}
        </div>
      )}

      <div className="language-groups">
        {Object.entries(filteredGroups).map(([group, langs]) => (
          <div key={group} className="language-group">
            <button
              type="button"
              className={`group-header ${expandedGroups.has(group) || search ? 'expanded' : ''}`}
              onClick={() => toggleGroup(group)}
              aria-expanded={expandedGroups.has(group) || !!search}
            >
              <Icons.ChevronRight />
              <span>{group}</span>
              <span className="group-count">{langs.length}</span>
            </button>
            {(expandedGroups.has(group) || search) && (
              <div className="group-languages" role="group" aria-label={`${group} languages`}>
                {langs.map(lang => {
                  const isSelected = multiple
                    ? selected.includes(lang)
                    : selected === lang;
                  return (
                    <div
                      key={lang}
                      className={`language-item ${isSelected ? 'selected' : ''}`}
                      onClick={() => handleSelect(lang)}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => e.key === 'Enter' && handleSelect(lang)}
                      aria-pressed={isSelected}
                    >
                      {multiple && (
                        <span className={`checkbox ${isSelected ? 'checked' : ''}`}>
                          {isSelected && <Icons.Check />}
                        </span>
                      )}
                      <span>{lang}</span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// Log entry component with timestamp and type
function LogEntry({ line, index }) {
  const isError = line.toLowerCase().includes('error') || line.toLowerCase().includes('failed');
  const isSuccess = line.toLowerCase().includes('success') || line.toLowerCase().includes('completed');
  const isProgress = line.includes('%') || line.toLowerCase().includes('processing');

  let type = 'info';
  if (isError) type = 'error';
  else if (isSuccess) type = 'success';
  else if (isProgress) type = 'progress';

  return (
    <div className={`log-entry ${type}`}>
      <span className="log-index">{String(index + 1).padStart(3, '0')}</span>
      <span className="log-content">{line}</span>
    </div>
  );
}

// Empty state component
function EmptyState({ icon: Icon, title, description }) {
  return (
    <div className="empty-state">
      <div className="empty-icon">
        <Icon />
      </div>
      <h3>{title}</h3>
      <p>{description}</p>
    </div>
  );
}

export default function App() {
  const [files, setFiles] = useState([]);
  const [selectedTargets, setSelectedTargets] = useState(["English", "Vietnamese"]);
  const [activeTarget, setActiveTarget] = useState(0);
  const [srcLang, setSrcLang] = useState("Auto");
  const model = "translategemma:12b";  // Hardcoded - single model
  const [includeHeaders, setIncludeHeaders] = useState(false);
  const [jobId, setJobId] = useState(null);
  const [jobStatus, setJobStatus] = useState(null);
  const [logs, setLogs] = useState([]);
  const [logCursor, setLogCursor] = useState(0);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [showSettings, setShowSettings] = useState(false);

  const fileInputRef = useRef(null);
  const logBoxRef = useRef(null);
  const dropZoneRef = useRef(null);

  // Calculate current step
  const currentStep = useMemo(() => {
    if (jobStatus?.status === "completed") return 3;
    if (jobId && jobStatus) return 2;
    if (files.length > 0 && selectedTargets.length > 0) return 1;
    return 0;
  }, [files, selectedTargets, jobId, jobStatus]);

  const steps = [
    { id: "upload", title: "Upload Files", desc: "Select documents to translate" },
    { id: "configure", title: "Configure", desc: "Choose languages & settings" },
    { id: "translate", title: "Translate", desc: "AI processing your files" },
    { id: "download", title: "Download", desc: "Get your translated files" }
  ];

  useEffect(() => {
    if (!jobId) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const status = await fetchJobStatus(jobId);
        if (!cancelled) setJobStatus(status);
      } catch (err) {
        if (!cancelled) setError(err.message || "Status polling failed");
      }
    };
    poll();
    const timer = setInterval(poll, 2000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [jobId]);

  useEffect(() => {
    if (!jobId) return undefined;
    const source = streamLogs(
      jobId,
      logCursor,
      (line) => {
        setLogs((prev) => [...prev, line]);
        setLogCursor((prev) => prev + 1);
      },
      () => {}
    );
    return () => source.close();
  }, [jobId]);

  // Auto-scroll logs
  useEffect(() => {
    if (logBoxRef.current) {
      logBoxRef.current.scrollTop = logBoxRef.current.scrollHeight;
    }
  }, [logs]);

  const isRunning = jobStatus?.status === "running";
  const canStart = useMemo(
    () => files.length > 0 && selectedTargets.length > 0 && !loading && !isRunning,
    [files, selectedTargets, loading, isRunning]
  );
  const outputReady = jobStatus?.output_ready;

  const progress = useMemo(() => {
    if (!jobStatus || jobStatus.total_files === 0) return 0;
    return (jobStatus.processed_files / jobStatus.total_files) * 100;
  }, [jobStatus]);

  const handleFileChange = (event) => {
    const incoming = Array.from(event.target.files || []);
    setFiles(prev => [...prev, ...incoming]);
    // Reset input value to allow selecting the same file again
    if (event.target) {
      event.target.value = '';
    }
  };

  const removeFile = (index) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
  };

  const toggleTarget = (lang) => {
    setSelectedTargets((prev) => {
      if (prev.includes(lang)) {
        const next = prev.filter((item) => item !== lang);
        return next.length ? next : prev;
      }
      return [...prev, lang];
    });
  };

  const moveTarget = (direction) => {
    setSelectedTargets((prev) => {
      const next = [...prev];
      if (activeTarget < 0 || activeTarget >= next.length) return prev;
      const newIndex = direction === "up" ? activeTarget - 1 : activeTarget + 1;
      if (newIndex < 0 || newIndex >= next.length) return prev;
      const [item] = next.splice(activeTarget, 1);
      next.splice(newIndex, 0, item);
      setActiveTarget(newIndex);
      return next;
    });
  };

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    // Only set dragging to false if we're leaving the drop zone
    const rect = dropZoneRef.current?.getBoundingClientRect();
    if (rect) {
      const { clientX, clientY } = e;
      if (
        clientX < rect.left ||
        clientX > rect.right ||
        clientY < rect.top ||
        clientY > rect.bottom
      ) {
        setIsDragging(false);
      }
    }
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const droppedFiles = Array.from(e.dataTransfer.files).filter(file => {
      const ext = file.name.split('.').pop().toLowerCase();
      return ['docx', 'pptx', 'xlsx', 'pdf'].includes(ext);
    });

    if (droppedFiles.length > 0) {
      setFiles(prev => [...prev, ...droppedFiles]);
    }
  }, []);

  const handleStart = async () => {
    setError(null);
    setLoading(true);
    setLogs([]);
    setLogCursor(0);
    try {
      const form = new FormData();
      files.forEach((file) => form.append("files", file));
      form.append("targets", selectedTargets.join(","));
      form.append("src_lang", srcLang);
      form.append("model", model);
      form.append("include_headers", String(includeHeaders));
      const response = await createJob(form);
      setJobId(response.job_id);
    } catch (err) {
      setError(err.message || "Failed to start job");
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = async () => {
    if (!jobId) return;
    try {
      await cancelJob(jobId);
    } catch (err) {
      setError(err.message || "Failed to cancel job");
    }
  };

  const handleReset = () => {
    setFiles([]);
    setJobId(null);
    setJobStatus(null);
    setLogs([]);
    setLogCursor(0);
    setError(null);
  };

  return (
    <div className="app">
      {/* Header */}
      <header className="header">
        <div className="header-content">
          <div className="logo">
            <div className="logo-icon">
              <Icons.Translate />
            </div>
            <div className="logo-text">
              <h1>Translate Tool</h1>
              <span>Local AI Translation Suite</span>
            </div>
          </div>
          <div className="header-badges">
            <span className="badge">Offline Ready</span>
            <span className="badge">55+ Languages</span>
            <span className="badge accent">FastAPI + Ollama</span>
          </div>
        </div>
      </header>

      {/* Step Indicator */}
      <div className="step-wrapper">
        <StepIndicator currentStep={currentStep} steps={steps} />
      </div>

      {/* Main Content */}
      <main className="main">
        {/* Left Column - Upload & Language Selection */}
        <div className="column column-left">
          {/* Upload Section */}
          <section className="card upload-card">
            <div className="card-header">
              <h2>
                <Icons.Upload />
                Upload Documents
              </h2>
              <span className="supported-formats">DOCX, PPTX, XLSX, PDF</span>
            </div>

            <div
              ref={dropZoneRef}
              className={`drop-zone ${isDragging ? 'dragging' : ''} ${files.length > 0 ? 'has-files' : ''}`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => e.key === 'Enter' && fileInputRef.current?.click()}
              aria-label="Upload files by clicking or dropping"
            >
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept=".docx,.pptx,.xlsx,.pdf"
                onChange={handleFileChange}
                style={{ display: 'none' }}
                aria-hidden="true"
              />
              <div className="drop-zone-content">
                <div className="drop-icon">
                  <Icons.Cloud />
                </div>
                <p className="drop-text">
                  <strong>Drop files here</strong> or <span className="link">browse</span>
                </p>
                <p className="drop-hint">Support for DOCX, PPTX, XLSX, and PDF files</p>
              </div>
            </div>

            {files.length > 0 && (
              <div className="file-list">
                <div className="file-list-header">
                  <span>{files.length} file{files.length > 1 ? 's' : ''} selected</span>
                  <button
                    type="button"
                    className="clear-all"
                    onClick={() => setFiles([])}
                    aria-label="Clear all files"
                  >
                    Clear all
                  </button>
                </div>
                <div className="file-cards">
                  {files.map((file, index) => (
                    <FileCard
                      key={`${file.name}-${file.size}-${index}`}
                      file={file}
                      onRemove={() => removeFile(index)}
                    />
                  ))}
                </div>
              </div>
            )}
          </section>

          {/* Source Language */}
          <section className="card language-card">
            <div className="card-header">
              <h2>
                <Icons.Globe />
                Source Language
              </h2>
              <span className="current-selection">{srcLang}</span>
            </div>
            <div className="language-card-content">
              <LanguageSelector
                selected={srcLang}
                onChange={setSrcLang}
              />
            </div>
          </section>
        </div>

        {/* Center Column - Target Languages */}
        <div className="column column-center">
          <section className="card targets-card">
            <div className="card-header">
              <h2>
                <Icons.Star />
                Target Languages
              </h2>
              <span className="selection-count">{selectedTargets.length} selected</span>
            </div>

            <div className="target-selection">
              <div className="language-selector-wrapper">
                <LanguageSelector
                  selected={selectedTargets}
                  onChange={toggleTarget}
                  multiple
                  excludeAuto
                />
              </div>

              <div className="output-order">
                <h3>Output Order</h3>
                <p className="order-hint">Click to select, then use arrows to reorder</p>
                <ul className="order-list" role="listbox" aria-label="Selected target languages">
                  {selectedTargets.map((lang, index) => (
                    <li
                      key={lang}
                      className={`order-item ${index === activeTarget ? "selected" : ""}`}
                      onClick={() => setActiveTarget(index)}
                      role="option"
                      aria-selected={index === activeTarget}
                      tabIndex={0}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') setActiveTarget(index);
                        if (e.key === 'ArrowUp') { setActiveTarget(index); moveTarget("up"); }
                        if (e.key === 'ArrowDown') { setActiveTarget(index); moveTarget("down"); }
                      }}
                    >
                      <span className="order-number">{index + 1}</span>
                      <span className="order-lang">{lang}</span>
                      <div className="order-actions">
                        <button
                          type="button"
                          disabled={index === 0}
                          onClick={(e) => { e.stopPropagation(); setActiveTarget(index); moveTarget("up"); }}
                          aria-label={`Move ${lang} up`}
                          title="Move up"
                        >
                          <Icons.ChevronUp />
                        </button>
                        <button
                          type="button"
                          disabled={index === selectedTargets.length - 1}
                          onClick={(e) => { e.stopPropagation(); setActiveTarget(index); moveTarget("down"); }}
                          aria-label={`Move ${lang} down`}
                          title="Move down"
                        >
                          <Icons.ChevronDown />
                        </button>
                        <button
                          type="button"
                          onClick={(e) => { e.stopPropagation(); toggleTarget(lang); }}
                          aria-label={`Remove ${lang}`}
                          title="Remove"
                        >
                          <Icons.X />
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
                {selectedTargets.length === 0 && (
                  <p className="no-targets">Select at least one target language</p>
                )}
              </div>
            </div>
          </section>
        </div>

        {/* Right Column - Settings & Actions */}
        <div className="column column-right">
          {/* Settings */}
          <section className="card settings-card">
            <button
              type="button"
              className="card-header collapsible"
              onClick={() => setShowSettings(!showSettings)}
              aria-expanded={showSettings}
              aria-controls="settings-content"
            >
              <h2>
                <Icons.Settings />
                Advanced Settings
              </h2>
              <svg
                className={`chevron ${showSettings ? 'open' : ''}`}
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </button>

            {showSettings && (
              <div className="settings-content" id="settings-content">
                <label className="toggle-setting">
                  <div className="toggle-switch">
                    <input
                      type="checkbox"
                      checked={includeHeaders}
                      onChange={(e) => setIncludeHeaders(e.target.checked)}
                      aria-label="翻譯頁首頁尾內容"
                    />
                    <span className="toggle-slider"></span>
                  </div>
                  <span>翻譯頁首頁尾內容（僅限 Windows）</span>
                </label>
              </div>
            )}
          </section>

          {/* Status & Progress */}
          <section className="card status-card">
            <div className="card-header">
              <h2>
                <Icons.Activity />
                Translation Status
              </h2>
              <StatusBadge status={jobStatus?.status || "idle"} />
            </div>

            <div className="status-content">
              {jobId ? (
                <>
                  <ProgressBar progress={progress} status={jobStatus?.status || "idle"} />
                  <div className="status-details">
                    <div className="status-item">
                      <span className="status-label">Files Processed</span>
                      <span className="status-value">
                        {jobStatus?.processed_files || 0} / {jobStatus?.total_files || 0}
                      </span>
                    </div>
                    <div className="status-item">
                      <span className="status-label">Job ID</span>
                      <span className="status-value job-id" title={jobId}>
                        {jobId.slice(0, 8)}...
                      </span>
                    </div>
                  </div>
                </>
              ) : (
                <div className="status-empty">
                  <Icons.FileText />
                  <p>Upload files and start translation to see progress</p>
                </div>
              )}

              {error && (
                <div className="error-message" role="alert">
                  <Icons.Error />
                  <span>{error}</span>
                </div>
              )}

              {jobStatus?.error && (
                <div className="error-message" role="alert">
                  <Icons.Error />
                  <span>{jobStatus.error}</span>
                </div>
              )}
            </div>

            {/* Action Buttons */}
            <div className="action-buttons">
              {!jobId || jobStatus?.status === "completed" || jobStatus?.status === "failed" || jobStatus?.status === "cancelled" ? (
                <>
                  <button
                    className="btn btn-primary"
                    onClick={handleStart}
                    disabled={!canStart}
                    aria-busy={loading}
                  >
                    {loading ? (
                      <>
                        <span className="spinner" aria-hidden="true"></span>
                        Starting...
                      </>
                    ) : (
                      <>
                        <Icons.Play />
                        Start Translation
                      </>
                    )}
                  </button>
                  {(jobStatus?.status === "completed" || jobStatus?.status === "failed" || jobStatus?.status === "cancelled") && (
                    <button className="btn btn-secondary" onClick={handleReset}>
                      <Icons.Refresh />
                      New Translation
                    </button>
                  )}
                </>
              ) : (
                <button className="btn btn-danger" onClick={handleCancel}>
                  <Icons.Stop />
                  Stop Translation
                </button>
              )}

              {outputReady && jobId && (
                <a
                  className="btn btn-success"
                  href={`/api/jobs/${jobId}/download`}
                  download
                >
                  <Icons.Download />
                  Download Files
                </a>
              )}
            </div>
          </section>
        </div>
      </main>

      {/* Logs Section */}
      {jobId && (
        <section className="card logs-card">
          <div className="card-header">
            <h2>
              <Icons.Terminal />
              Translation Logs
            </h2>
            <span className="log-count">{logs.length} entries</span>
          </div>
          <div
            className="log-box"
            ref={logBoxRef}
            role="log"
            aria-live="polite"
            aria-label="Translation logs"
          >
            {logs.length === 0 ? (
              <div className="log-placeholder">
                <Icons.Clock />
                <p>Waiting for logs...</p>
              </div>
            ) : (
              logs.map((line, index) => (
                <LogEntry key={`${index}-${line.slice(0, 20)}`} line={line} index={index} />
              ))
            )}
          </div>
        </section>
      )}

      {/* Footer */}
      <footer className="footer">
        <p>Local AI Translation Suite - Powered by FastAPI + Ollama</p>
        <div className="footer-links">
          <span>Privacy-first</span>
          <span>Offline-capable</span>
          <span>Open Source</span>
        </div>
      </footer>
    </div>
  );
}
