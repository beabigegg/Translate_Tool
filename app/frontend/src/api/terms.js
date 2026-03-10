import { get, post, patch } from './client.js';

export const fetchTermStats = () => get('/api/terms/stats');

export function getTermExportUrl(format, status) {
  const params = new URLSearchParams({ format });
  if (status && status !== 'all') params.set('status', status);
  return `/api/terms/export?${params}`;
}

export function fetchApprovedTerms(targetLang, domain) {
  const params = new URLSearchParams();
  if (targetLang) params.set('target_lang', targetLang);
  if (domain) params.set('domain', domain);
  const qs = params.toString() ? `?${params}` : '';
  return get(`/api/terms/approved${qs}`);
}

export function fetchUnverifiedTerms(targetLang, domain) {
  const params = new URLSearchParams();
  if (targetLang) params.set('target_lang', targetLang);
  if (domain) params.set('domain', domain);
  const qs = params.toString() ? `?${params}` : '';
  return get(`/api/terms/unverified${qs}`);
}

export function approveTerm(sourceText, targetLang, domain) {
  return post('/api/terms/approve', JSON.stringify({ source_text: sourceText, target_lang: targetLang, domain }), {
    headers: { 'Content-Type': 'application/json' }
  });
}

export function editTerm(sourceText, targetLang, domain, targetText, confidence) {
  const body = { source_text: sourceText, target_lang: targetLang, domain, target_text: targetText };
  if (confidence !== undefined) body.confidence = confidence;
  return patch('/api/terms/edit', body);
}

export async function importTerms(file, strategy = 'skip') {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch(`/api/terms/import?strategy=${encodeURIComponent(strategy)}`, {
    method: 'POST', body: formData,
  });
  if (!res.ok) {
    const payload = await res.json().catch(() => ({}));
    throw new Error(payload.detail || 'Import failed');
  }
  return res.json();
}
