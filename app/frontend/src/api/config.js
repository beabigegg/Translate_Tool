import { get } from './client.js';

const MODEL_CONFIG_FALLBACK = [
  { model_type: 'general', model_size_gb: 3.5, kv_per_1k_ctx_gb: 0.35, default_num_ctx: 4096, min_num_ctx: 1024, max_num_ctx: 8192 },
  { model_type: 'translation', model_size_gb: 5.7, kv_per_1k_ctx_gb: 0.22, default_num_ctx: 3072, min_num_ctx: 1024, max_num_ctx: 8192 },
];

export const fetchProfiles = () => get('/api/profiles');
export const fetchRouteInfo = (targets) => {
  if (!targets || targets.length === 0) return Promise.resolve({ routes: [] });
  return get(`/api/route-info?targets=${encodeURIComponent(targets.join(','))}`).catch(() => ({ routes: [] }));
};
export async function fetchModelConfig() {
  try {
    const payload = await get('/api/model-config');
    if (Array.isArray(payload) && payload.length > 0) return payload;
  } catch (err) {
    console.warn('Failed to fetch model config, using fallback:', err);
  }
  return MODEL_CONFIG_FALLBACK;
}
