# Facet R2 gate (b) — anchor-noise + hygiene sweep

**Date:** 2026-07-06. **Question:** does FACET-as-reranker survive REAL anchor quality?
Menhir's `hybrid` facet mode reads structural facets (file/symbol) from the graph as a
*gold stand-in* — it assumes `ANCHORED_TO`/`DEFINES` anchors are correct. Gate (b) tests
that assumption with gold relevance labels.

## Real anchor quality (measured, live-menhir clone, dummy 7687)

`menhir-frontier/scripts/_measure_anchor_quality.py` (read-only on the bolt clone of prod):

- **11,706 anchor pairs / 1300 memories = mean 9.0 files/memory** (max **215**) — massive
  over-anchoring.
- **~75% of anchors are text-unsupported** (memory content never mentions the anchored
  file stem or any DEFINES symbol); only **25%** text-supported.
- **Boilerplate magnets:** `pyproject.toml` on 239 memories, `tests/__init__.py` 118,
  `app/main.py` (DEFINES 51 symbols) 110.
- 17% of files DEFINE ≥10 symbols → noisy symbol facets.

So the real noise model is **dominant spurious over-anchoring + frequent true-anchor
loss**, not gentle drop/swap.

## The regime (`archolith_bench/facet/anchor_noise.py`)

Calibrated corpus transforms, applied to the `hybrid` corpus via the runner's new optional
`corpus_transform` hook (default None == today's behavior; correctness always judged
against the untouched gold corpus). Only file/symbol facets are altered — scope/belief come
from metadata and stay intact (the reliable fashion).

- `inject_anchor_noise` — pile spurious file/symbol anchors (boilerplate + plausible
  cross-memory neighbors) to mean ~9/mem; `true_drop_frac` also drops a fraction of each
  memory's *true* anchors (the correct link the scanner missed), so the right answer can
  actually lose its convergence. A memory's own true anchors are excluded from its spurious
  pool (else a dropped true anchor could be silently re-added).
- `apply_anchor_hygiene` — `text_support` (keep only anchors whose tokens appear in the
  memory text), `boilerplate` (drop magnets + boilerplate list), `cap` (keep ≤k, prefer
  text-supported).

## Result (`scripts/_gate_b_anchor_sweep.py`, hybrid mode, F = facet meet-point)

| regime | anchors/mem | recall@5 | wrong_scope↓ | support_suff | gate |
|---|---|---|---|---|---|
| clean | 1.8 | 0.825 | 0.070 | 0.800 | GRAD |
| +noise drop=0.0 | 8.7 | 0.825 | 0.110 | 0.800 | GRAD |
| +noise drop=0.5 | 8.6 | 0.825 | 0.100 | 0.800 | GRAD |
| **+noise drop=1.0** | 8.5 | **0.850** | 0.100 | 0.850 | **GRAD** |
| +noise0.5 +hy:text_support | 1.4 | 0.850 | 0.070 | 0.850 | GRAD |
| +noise0.5 +hy:boilerplate | 4.8 | 0.825 | 0.110 | 0.800 | GRAD |
| +noise0.5 +hy:cap | 5.5 | 0.825 | 0.110 | 0.800 | GRAD |

Same verdict under a real OpenAI embedder (F is embedder-independent; the run only makes
the baselines it beats real). Baseline wrong_scope for reference is ~0.40.

## Finding

**F is robust to real anchor noise — including total (drop=1.0) true-structural-anchor
loss.** recall holds/rises, wrong_scope stays 0.07–0.11 (vs 0.40 baseline). The reranker's
win is **scope/belief discipline (noise-free metadata) + interpretive overlap**, NOT
structural convergence — file/symbol were always a minor bonus, and the sweep shows they can
be 100% corrupted with no collapse. This *inverts* the gate-(a) dummy alarm: the dummy looked
catastrophic only because that measurement ran raw structural convergence WITHOUT scope
discipline; with scope discipline (in-reranker here, or menhir's ScopeWarden), noise is a
non-issue.

**Gate (b) verdict: anchor quality is NOT a blocker for Phase-4.** Hygiene is therefore
optional (nice-to-have precision, not a gate) — `text_support` cleanly restores density
(1.4/mem) but the win doesn't depend on it.

**The catch it surfaces (for Phase-4 go/no-go):** because the win is scope/belief and those
are already menhir's `ScopeWarden`/`CurrentnessWarden` job, FACET-as-reranker's *net-new over
the existing warden chain* is thin. Structural convergence — the one thing wardens don't do —
is negligible and noise-poisoned on the real graph. So gate (b) passing on robustness does
not by itself justify wiring FACET active; that decision hinges on whether facet candidate
generation surfaces topically-related memories (operation/object overlap) that vector recall
misses — measured separately, and on the live A/B (gate c).

## Reproduce

```
python scripts/_gate_b_anchor_sweep.py                    # stub embedder
python scripts/_gate_b_anchor_sweep.py --embedder openai  # real baselines
```
