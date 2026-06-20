const BASE = import.meta.env.VITE_API_BASE ?? '';

async function getJson(url) {
  const r = await fetch(BASE + url);
  if (r.status === 404) return null;
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

export const getLayoutViz = (jobId) => getJson(`/api/jobs/${jobId}/layout`);
