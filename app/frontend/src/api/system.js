import { get, del } from './client.js';
export const fetchHealth = () => get('/api/health');
export const fetchStats = () => get('/api/stats');
export const fetchCacheStats = () => get('/api/cache/stats');
export const clearCache = () => del('/api/cache');
