const BASE = '';

async function request(path, options = {}) {
  const res = await fetch(BASE + path, options);
  if (!res.ok) {
    const payload = await res.json().catch(() => ({}));
    throw new Error(payload.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export const get = (path) => request(path);
export const post = (path, body, opts = {}) => request(path, { method: 'POST', ...opts, body });
export const del = (path) => request(path, { method: 'DELETE' });
export const patch = (path, data) => request(path, {
  method: 'PATCH',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(data),
});
