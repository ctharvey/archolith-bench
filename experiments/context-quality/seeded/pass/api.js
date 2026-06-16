// api.js — shared Yawn API client
export async function api(path, params = {}) {
  const qs = new URLSearchParams(params).toString();
  const r = await fetch(`/api${path}${qs ? '?' + qs : ''}`);
  if (!r.ok) throw new Error(`api ${path} ${r.status}`);
  return r.json();
}
export const setsMatrix    = (p) => api('/sets/matrix', p);
export const marketBreadth = (p) => api('/market/breadth', p);
export const cardSearch    = (p) => api('/card/search', p);
export const cardDetail    = (p) => api('/card/detail', p);
export const sealedList    = (p) => api('/sealed/list', p);
export const sealedDetail  = (p) => api('/sealed/detail', p);
export const graded        = (p) => api('/graded', p);
export const setsList      = (p) => api('/sets/list', p);
export const setDetail     = (p) => api('/sets/detail', p);
export const series        = (p) => api('/series', p);
export const transactions  = (p) => api('/transactions', p);
export const vsCompare     = (p) => api('/vs/compare', p);
