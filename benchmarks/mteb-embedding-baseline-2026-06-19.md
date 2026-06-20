# MTEB embedding-model baseline — 2026-06-19

**Type:** Single-arm embedding-model baseline (NOT a proxy A/B). MTEB measures embedding
quality; the Archolith chat proxy is not in the embeddings path. This number describes the
embedding model that menhir / fact-retrieval depends on, not the proxy.

**Harness:** Official MTEB 2.15.5 + `datasets`, real SciFact retrieval dataset.
**Runner:** `scripts/run_mteb_local.py` (in-process `AbsEncoder` subclass calling an
OpenAI-compatible `/embeddings` endpoint).

| Model | Endpoint | Task | Metric | Score |
|-------|----------|------|--------|-------|
| `text-embedding-nomic-embed-text-v1.5` | LM Studio `localhost:1234/v1` (local, free) | SciFact | NDCG@10 (main_score) | **0.68115** |

## Context

- menhir's **active** embedder is OpenAI `text-embedding-3-small` (1536-dim), per
  `GRAPHITI_EMBED_PROVIDER=openai` / `OPENAI_EMBED_MODEL`. Published MTEB SciFact for that model
  is ~0.73 NDCG@10. The local nomic baseline here (0.68) is ~5 points behind — relevant to a
  "drop to free local embeddings" decision for menhir.
- menhir also has a *configured but inactive* local embed path at `localhost:8083/v1`
  (llama.cpp `nomic-embed-text-v1.5.Q4_K_M.gguf`) — a different endpoint from the LM Studio
  `:1234` server benchmarked here, and a different quantization (Q4_K_M).

## Caveats / not-yet

- One task (SciFact), one model. Not a full MTEB suite run.
- `text-embedding-3-small` not yet run head-to-head here (needs the OpenAI key; cheap). The
  ~0.73 figure is the published leaderboard value, not a local re-run.
- This is a baseline, not an advertisable "Archolith score." A proxy A/B requires an embeddings
  proxy/caching layer that does not exist.

## Reproduce

```bash
pip install mteb
python scripts/run_mteb_local.py SciFact
# EMBEDDINGS_BASE_URL / EMBEDDINGS_MODEL override the endpoint/model.
```
