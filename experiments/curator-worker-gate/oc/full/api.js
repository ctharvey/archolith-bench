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
export const seriesList     = (p) => api('/series', p);
export const transactions   = (p) => api('/transactions', p);
export const tradesList     = (p) => api('/transactions', p);
export const vsCompare     = (p) => api('/vs/compare', p);
export const decksList      = (p) => api('/decks/list', p);
export const watchlist       = (p) => api('/watchlist', p);
export const portfolio        = (p) => api('/portfolio', p);
export const searchAll        = (p) => api('/search', p);
export const history           = (p) => api('/history', p);
export const stats               = (p) => api('/stats', p);
export const wishlist            = (p) => api('/wishlist', p);
export const activity             = (p) => api('/activity', p);
export const notifications         = (p) => api('/notifications', p);
export const settings               = (p) => api('/settings', p);
export const help                     = (p) => api('/help', p);
export const about                     = (p) => api('/about', p);
export const login                       = (p) => api('/login', p);
export const signup                      = (p) => api('/signup', p);
