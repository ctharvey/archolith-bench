const BASE = "/api";

export async function api(path, params = {}) {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null) qs.set(k, v);
  }
  const url = `${BASE}${path}${qs.toString() ? "?" + qs : ""}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.json();
}

/* ── named helpers ── */

export function setsMatrix(q, tier) {
  return api("/sets/matrix", { q, tier });
}

export function marketBreadth(setId, grade) {
  return api("/market/breadth", { setId, grade });
}

export function cardSearch(q, set, grade, sort, limit, offset) {
  return api("/cards/search", { q, set, grade, sort, limit, offset });
}

export function cardDetail(id) {
  return api("/cards/" + encodeURIComponent(id));
}

export function sealedList(q, sort, limit, offset) {
  return api("/sealed/list", { q, sort, limit, offset });
}

export function sealedDetail(id) {
  return api("/sealed/" + encodeURIComponent(id));
}

export function graded(cardId, limit, offset) {
  return api("/cards/" + encodeURIComponent(cardId) + "/grades", { limit, offset });
}

export function setsList(q, sort) {
  return api("/sets/list", { q, sort });
}

export function setDetail(code) {
  return api("/sets/" + encodeURIComponent(code));
}

export function series() {
  return api("/series");
}

export function transactions(cardId, limit, offset) {
  return api("/cards/" + encodeURIComponent(cardId) + "/txns", { limit, offset });
}

export function vsCompare(cardIds, grade) {
  return api("/vs/compare", { ids: cardIds?.join(","), grade });
}