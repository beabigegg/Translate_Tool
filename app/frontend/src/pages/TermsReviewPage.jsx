import React, { useEffect, useState, useRef } from 'react';
import { toast } from 'sonner';
import { Button } from '../components/ui/Button.jsx';
import { Spinner } from '../components/feedback/Spinner.jsx';
import { fetchUnverifiedTerms, approveTerm, editTerm } from '../api/terms.js';

function TermCard({ term, onApproved }) {
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState(term.target_text);
  const inputRef = useRef(null);

  useEffect(() => { if (editing) inputRef.current?.focus(); }, [editing]);

  async function handleApprove(targetText) {
    try {
      if (targetText !== term.target_text) {
        await editTerm(term.source_text, term.target_lang, term.domain, targetText, 1.0);
      }
      await approveTerm(term.source_text, term.target_lang, term.domain);
      toast.success(`術語已核准：${term.source_text} → ${targetText}`);
      onApproved(term);
    } catch (err) {
      toast.error(err.message);
    }
  }

  return (
    <div className="term-card">
      <div className="term-card-source">{term.source_text}</div>
      <div className="term-card-arrow">→</div>
      <div className="term-card-target">
        {editing ? (
          <input
            ref={inputRef}
            value={editValue}
            onChange={e => setEditValue(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter') { handleApprove(editValue); setEditing(false); }
              if (e.key === 'Escape') { setEditing(false); setEditValue(term.target_text); }
            }}
            className="form-input"
          />
        ) : <span>{term.target_text}</span>}
      </div>
      <div className="term-card-meta">
        <span>{term.target_lang}</span>
        <span>{term.domain}</span>
        <span>{(term.confidence * 100).toFixed(0)}%</span>
      </div>
      <div className="term-card-actions">
        <Button size="sm" variant="ghost" onClick={() => setEditing(v => !v)}>編輯</Button>
        <Button size="sm" onClick={() => handleApprove(editValue)}>核准</Button>
      </div>
    </div>
  );
}

export default function TermsReviewPage() {
  const [terms, setTerms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [langFilter, setLangFilter] = useState('');
  const [domainFilter, setDomainFilter] = useState('');
  const [search, setSearch] = useState('');

  async function load() {
    setLoading(true);
    try {
      const data = await fetchUnverifiedTerms(langFilter, domainFilter);
      setTerms(data);
    } catch (err) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [langFilter, domainFilter]);

  const filtered = terms.filter(t =>
    !search || t.source_text.includes(search) || t.target_text.includes(search)
  );

  function handleApproved(term) {
    setTerms(prev => prev.filter(t => !(t.source_text === term.source_text && t.target_lang === term.target_lang && t.domain === term.domain)));
  }

  async function handleApproveAll() {
    if (!window.confirm(`確認核准全部 ${filtered.length} 筆術語？`)) return;
    let count = 0;
    for (const t of filtered) {
      try { await approveTerm(t.source_text, t.target_lang, t.domain); count++; } catch { /* skip */ }
    }
    toast.success(`已核准 ${count} 筆術語`);
    await load();
  }

  const langs = [...new Set(terms.map(t => t.target_lang))];
  const domains = [...new Set(terms.map(t => t.domain))];

  return (
    <div className="terms-review-page">
      <div className="page-header">
        <h2 className="page-title">術語審核</h2>
        {filtered.length > 0 && <Button onClick={handleApproveAll}>全部核准 ({filtered.length})</Button>}
      </div>
      <div className="review-filters">
        <input className="form-input" placeholder="搜尋..." value={search} onChange={e => setSearch(e.target.value)} />
        <select className="form-select" value={langFilter} onChange={e => setLangFilter(e.target.value)}>
          <option value="">所有語言</option>
          {langs.map(l => <option key={l} value={l}>{l}</option>)}
        </select>
        <select className="form-select" value={domainFilter} onChange={e => setDomainFilter(e.target.value)}>
          <option value="">所有領域</option>
          {domains.map(d => <option key={d} value={d}>{d}</option>)}
        </select>
      </div>
      {loading ? <Spinner /> : filtered.length === 0
        ? <p className="text-muted">無待審核術語</p>
        : <div className="term-card-list">{filtered.map((t, i) => <TermCard key={i} term={t} onApproved={handleApproved} />)}</div>
      }
    </div>
  );
}
