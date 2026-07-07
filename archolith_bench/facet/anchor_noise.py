"""Anchor-noise + hygiene corpus transforms (R2 gate-b anchor-quality regime).

The facet ladder's `hybrid` mode reads structural facets (file/symbol) as a *gold
stand-in* — it assumes the graph's ANCHORED_TO/DEFINES anchors are correct. Measured on
the live-menhir clone that assumption is false: mean ~9 anchors/memory (max 215), ~75%
text-unsupported, heavy boilerplate concentration (pyproject.toml on 239 memories). This
module models that regime on a labeled fixture so gate (b) can ask two questions with
gold relevance labels:

  1. inject_anchor_noise  — does F (facet meet-point) collapse under realistic spurious
     over-anchoring, the way it did on the noisy dummy?
  2. apply_anchor_hygiene — does a cheap ingest-side filter (text-support / boilerplate /
     cap) RECOVER the structural win by stripping the spurious anchors back out?

Both are pure, deterministic (seeded), and non-mutating: they return fresh Memory objects
so the fixture's gold corpus is untouched. Only file/symbol facets are altered — scope
(repo/project/namespace) and belief come from metadata and are left intact (the reliable
fashion). Faithfulness caveat: the fixture's gold anchors are text-supported, unlike the
real 25%, so text-support hygiene is optimistic here; boilerplate/cap modes are not.
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass

from .models import Memory, MemoryFacetSet

# Boilerplate files mirroring the real magnets measured on the clone (pyproject.toml on
# 239 memories, tests/__init__.py 118, app/main.py 110, ...). Injected as spurious anchors
# that carry ~no discriminating signal — the noise a scanner piles on via shared structure.
BOILERPLATE_FILES: tuple[str, ...] = (
    "pyproject.toml", "setup.py", "setup.cfg", ".agent/project.toml",
    "tests/__init__.py", "tests/conftest.py", "src/__init__.py", "__init__.py",
    "app/main.py", "src/main.py", "scripts/main.py", "README.md", "Makefile",
)

_WORD = re.compile(r"[a-z0-9_]+")


def _copy_facets(f: MemoryFacetSet) -> MemoryFacetSet:
    return MemoryFacetSet.from_dict(f.to_dict())


def _stem(path: str) -> str:
    base = path.replace("\\", "/").rsplit("/", 1)[-1]
    return base.rsplit(".", 1)[0] if "." in base else base


def _name_parts(name: str) -> set[str]:
    """Discriminating tokens of a file stem or symbol (snake + camel split, len>2)."""
    low = name.lower()
    parts = {p for p in re.split(r"[_\W]+", low) if len(p) > 2}
    parts.update(p.lower() for p in re.findall(r"[A-Z]?[a-z]{3,}", name))
    parts.add(low)
    return parts


def _text_supported(text_tokens: set[str], name: str, *, stem: bool) -> bool:
    key = _stem(name) if stem else name
    return bool(_name_parts(key) & text_tokens)


@dataclass
class AnchorNoiseConfig:
    """Real anchor regime calibrated to the measurement (mean 9, ~75% spurious).

    Two effects, both observed on the clone: over-anchoring (spurious files/symbols piled
    on) AND true-anchor loss (the correct file/symbol often missing/wrong, so the right
    answer has no real convergence to win with). ``true_drop_frac`` models the second —
    without it, over-anchoring alone can't collapse F because the gold answer keeps full
    convergence and always out-scores the partial spurious matches.
    """

    target_anchors: int = 9          # total file+symbol anchors per memory after injection
    spurious_min: int = 4            # never inject fewer than this (small-anchor memories)
    boilerplate_ratio: float = 0.4   # share of spurious files drawn from BOILERPLATE_FILES
    true_drop_frac: float = 0.0      # fraction of each memory's TRUE file/symbol anchors to drop
    seed: int = 1234


def inject_anchor_noise(
    memories: list[Memory], config: AnchorNoiseConfig | None = None
) -> list[Memory]:
    """Return a copy of the corpus with spurious file/symbol anchors piled on.

    True anchors are preserved (hygiene must be able to recover them); spurious anchors are
    drawn from BOILERPLATE + other memories' real files/symbols (plausible neighbors, so
    some coincidentally share query tokens — noise that a text filter can't perfectly strip).
    """
    cfg = config or AnchorNoiseConfig()
    file_pool = sorted({f for m in memories for f in m.facets.file})
    symbol_pool = sorted({s for m in memories for s in m.facets.symbol})
    out: list[Memory] = []
    for m in memories:
        rng = random.Random(f"{cfg.seed}:{m.id}")
        facets = _copy_facets(m.facets)
        # A memory's OWN true anchors are never valid spurious picks — otherwise a dropped
        # true anchor could be re-added as "spurious", silently undoing true_drop_frac.
        own_files, own_symbols = set(m.facets.file), set(m.facets.symbol)
        # (c) true-anchor loss: drop a fraction of the correct anchors (scanner missed the
        # real link) so the right answer can actually lose its convergence.
        if cfg.true_drop_frac > 0:
            facets.file = _drop_frac(facets.file, cfg.true_drop_frac, rng)
            facets.symbol = _drop_frac(facets.symbol, cfg.true_drop_frac, rng)
        have = len(facets.file) + len(facets.symbol)
        want_spurious = max(cfg.spurious_min, cfg.target_anchors - have)

        for _ in range(want_spurious):
            if rng.random() < cfg.boilerplate_ratio:
                facets.file.add(rng.choice(BOILERPLATE_FILES))
            elif symbol_pool and rng.random() < 0.5:
                cand = rng.choice(symbol_pool)
                if cand not in own_symbols:
                    facets.symbol.add(cand)
            elif file_pool:
                cand = rng.choice(file_pool)
                if cand not in own_files:
                    facets.file.add(cand)
        out.append(Memory(id=m.id, text=m.text, facets=facets, superseded=m.superseded))
    return out


@dataclass
class AnchorHygieneConfig:
    """Ingest-side anchor filter. mode: 'text_support' | 'boilerplate' | 'cap'."""

    mode: str = "text_support"
    cap_k: int = 3                   # for 'cap': max structural anchors kept per memory
    multiplicity_frac: float = 0.15  # for 'boilerplate': drop files anchored by > this frac of corpus
    multiplicity_min: int = 3        # ...and by at least this many memories (floor for tiny corpora)


def apply_anchor_hygiene(
    memories: list[Memory], config: AnchorHygieneConfig | None = None
) -> list[Memory]:
    """Return a copy of the corpus with low-quality structural anchors filtered out.

    - text_support: keep only file/symbol anchors whose tokens appear in the memory text.
    - boilerplate:  drop BOILERPLATE files + any file anchored by > multiplicity_frac of the
      corpus (data-driven magnet detection), independent of text.
    - cap:          keep at most cap_k structural anchors, preferring text-supported ones.
    """
    cfg = config or AnchorHygieneConfig()
    if cfg.mode == "boilerplate":
        n = len(memories)
        file_mult: dict[str, int] = {}
        for m in memories:
            for f in m.facets.file:
                file_mult[f] = file_mult.get(f, 0) + 1
        threshold = max(cfg.multiplicity_min, cfg.multiplicity_frac * n)
        magnets = {f for f, c in file_mult.items() if c > threshold}
        block = magnets | set(BOILERPLATE_FILES)

    out: list[Memory] = []
    for m in memories:
        facets = _copy_facets(m.facets)
        ttok = set(_WORD.findall(m.text.lower()))
        if cfg.mode == "text_support":
            facets.file = {f for f in facets.file if _text_supported(ttok, f, stem=True)}
            facets.symbol = {s for s in facets.symbol if _text_supported(ttok, s, stem=False)}
        elif cfg.mode == "boilerplate":
            facets.file = {f for f in facets.file if f not in block}
        elif cfg.mode == "cap":
            facets.file = _cap(facets.file, ttok, cfg.cap_k, stem=True)
            facets.symbol = _cap(facets.symbol, ttok, cfg.cap_k, stem=False)
        else:
            raise ValueError(f"unknown hygiene mode: {cfg.mode!r}")
        out.append(Memory(id=m.id, text=m.text, facets=facets, superseded=m.superseded))
    return out


def _cap(values: set[str], ttok: set[str], k: int, *, stem: bool) -> set[str]:
    ranked = sorted(values, key=lambda v: (not _text_supported(ttok, v, stem=stem), v))
    return set(ranked[:k])


def _drop_frac(values: set[str], frac: float, rng: random.Random) -> set[str]:
    """Drop ~frac of the values (deterministic given rng). Keeps at least the remainder."""
    keep = sorted(values)
    n_drop = int(round(len(keep) * frac))
    if n_drop <= 0:
        return set(keep)
    rng.shuffle(keep)
    return set(keep[n_drop:])
