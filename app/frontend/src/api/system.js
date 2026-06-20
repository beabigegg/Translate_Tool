import { get, del, post } from './client.js';
export const fetchHealth = () => get('/api/health');
export const fetchStats = () => get('/api/stats');
export const fetchCacheStats = () => get('/api/cache/stats');
export const clearCache = () => del('/api/cache');

export async function getProviderHealth(deepseekApiKey = null) {
  const headers = {};
  if (deepseekApiKey) {
    headers['X-DeepSeek-Api-Key'] = deepseekApiKey;
  }
  const res = await fetch('/api/providers/health', { headers });
  if (!res.ok) {
    const payload = await res.json().catch(() => ({}));
    throw new Error(payload.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export function getProviderModels() {
  return get('/api/providers/models');
}

export function testTranslation(payload) {
  return post(
    '/api/providers/test-translation',
    JSON.stringify(payload),
    { headers: { 'Content-Type': 'application/json' } }
  );
}
