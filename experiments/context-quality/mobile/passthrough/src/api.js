const API_BASE = "/api";

/** Shared fetch wrapper with JSON error handling */
async function api(path, params = {}) {
  const url = new URL(path, window.location.origin);
  url.pathname = API_BASE + path;
  Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
  const res = await fetch(url);
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.json();
}

/* ---- Named helpers ---- */

export function setsMatrix(opts = {}) {
  return api("/sets/matrix", opts);
}

export function marketBreadth(opts = {}) {
  return api("/market/breadth", opts);
}

export function cardSearch(query, opts = {}) {
  return api("/cards/search", { q: query, ...opts });
}

export function cardDetail(id, opts = {}) {
  return api("/cards/detail", { id, ...opts });
}

export function sealedList(opts = {}) {
  return api("/sealed/list", opts);
}

export function sealedDetail(id, opts = {}) {
  return api("/sealed/detail", { id, ...opts });
}

export function graded(category, opts = {}) {
  return api("/graded/list", { category, ...opts });
}

export function setsList(opts = {}) {
  return api("/sets/list", opts);
}

export function setDetail(id, opts = {}) {
  return api("/sets/detail", { id, ...opts });
}

export function series(opts = {}) {
  return api("/series", opts);
}

export function transactions(opts = {}) {
  return api("/transactions", opts);
}

export function vsCompare(left, right, opts = {}) {
  return api("/vs/compare", { left, right, ...opts });
}