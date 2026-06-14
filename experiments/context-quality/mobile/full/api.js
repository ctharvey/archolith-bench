const BASE = '/api';

export async function api(path, params = {}) {
  const qs = params ? '?' + new URLSearchParams(params) : '';
  const res = await fetch(`${BASE}${path}${qs}`);
  if (!res.ok) throw new Error(`${res.status} on ${path}`);
  return res.json();
}

// ────── Named helpers ──────
export const setsMatrix       = (p) => api('/sets/matrix', p);
export const marketBreadth   = (p) => api('/market/breadth', p);
export const cardSearch       = (p) => api('/cards/search', p);
export const cardDetail       = (p) => api('/cards/detail', p);
export const sealedList       = (p) => api('/sealed/list', p);
export const sealedDetail     = (p) => api('/sealed/detail', p);
export const graded           = (p) => api('/graded', p);
export const setsList         = (p) => api('/sets/list', p);
export const setDetail        = (p) => api('/sets/detail', p);
export const series           = (p) => api('/series', p);
export const transactions     = (p) => api('/transactions', p);
export const vsCompare        = (p) => api('/vs/compare', p);