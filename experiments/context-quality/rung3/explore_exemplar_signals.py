#!/usr/bin/env python3
"""EXPLORATION: what signal surfaces an "exemplar" across corpus types?

The production miner (corpus_profile.py) uses ONE signal — recurring PascalCase
trailing-word+ext across sibling dirs — which finds `Page.tsx` in a feature-folder
React app but NOTHING in opencode (domain modules) or Python. This script tries
THREE candidate signals per corpus to learn what it would take to determine
exemplars more generally. Offline, no LLM. Not production code — a probe.

  A  name-varying template : recurring `<Word><ext>` PascalCase suffix (current miner)
  B  fixed-name convention : recurring EXACT basename across dirs (catches schema.ts,
                             base.py, models.py) with boilerplate filtered out
  C  recurring DIR SHAPE   : directories that share the same SET of file-roles -- the
                             "template" generalized from one file to a co-located role set

Usage: python rung3/explore_exemplar_signals.py <src-root> [lang]
"""
from __future__ import annotations

import posixpath
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from analyze_corpus import load_corpus, _EXTS  # noqa: E402

# Tokenizer that keeps ALL-CAPS acronyms whole: "CardDTO" -> ["Card","DTO"] (not ...,"O").
_PASCAL = re.compile(r"[A-Z]+(?![a-z])|[A-Z][a-z0-9]*")
# boilerplate / structural files that are conventions but not "templates to imitate"
_NOISE = {"__init__.py", "index.ts", "index.tsx", "index.js", "mod.ts", "__main__.py"}


def _stem_ext(base: str) -> tuple[str, str]:
    parts = base.split(".")
    return (parts[0], "." + ".".join(parts[1:])) if len(parts) > 1 else (parts[0], "")


def _pascal_suffix(base: str) -> str | None:
    stem, ext = _stem_ext(base)
    if not ext:
        return None
    words = _PASCAL.findall(stem)
    return words[-1] + ext if words else None


def _role(base: str) -> str:
    """A file's role token: PascalCase suffix if present, else the exact basename."""
    return _pascal_suffix(base) or base


def explore(root: Path):
    files, _ = load_corpus(root)
    paths = [getattr(f, "path", "").replace("\\", "/") for f in files]
    by_dir: dict[str, list[str]] = defaultdict(list)
    for p in paths:
        by_dir[posixpath.dirname(p)].append(posixpath.basename(p))

    # Signal A — name-varying PascalCase template suffix, #distinct dirs AND #files
    # (#dirs surfaces feature-folder corpora; #files surfaces layer-package corpora
    #  like Java/Spring where one role fills one package dir).
    a_dirs = defaultdict(set)
    a_files = Counter()
    for p in paths:
        pat = _pascal_suffix(posixpath.basename(p))
        if pat:
            a_dirs[pat].add(posixpath.dirname(p))
            a_files[pat] += 1
    sig_a = sorted(((k, len(v), a_files[k]) for k, v in a_dirs.items()),
                   key=lambda t: -t[2])  # rank by file count

    # Signal B — fixed-name convention: exact basename across dirs, noise filtered
    b = defaultdict(set)
    for p in paths:
        base = posixpath.basename(p)
        if base in _NOISE:
            continue
        b[base].add(posixpath.dirname(p))
    sig_b = sorted(((k, len(v)) for k, v in b.items() if len(v) >= 2), key=lambda kv: -kv[1])

    # Signal C — recurring DIR SHAPE: the set of file-roles co-located in a dir
    shape_dirs: dict[frozenset, list[str]] = defaultdict(list)
    for d, bases in by_dir.items():
        roles = frozenset(_role(b) for b in bases if b not in _NOISE)
        if len(roles) >= 2:                      # ignore trivial 1-file dirs
            shape_dirs[roles].append(d)
    sig_c = sorted(
        ((shape, dirs) for shape, dirs in shape_dirs.items() if len(dirs) >= 2),
        key=lambda kv: (-len(kv[1]), -len(kv[0])),
    )

    # Signal E — cross-layer STEM FAMILY (the layer-package analog of C): group files
    # by entity stem; the recurring set of ROLE suffixes a stem carries is the feature
    # template. Restrict roles to the derived role vocabulary (top sig_a words) so
    # coincidental stem-sharing (Delta/Api/App) drops out.
    role_vocab = {_stem_ext(k)[0].lstrip(".") or k.split(".")[0]: None for k, _d, _n in sig_a[:8]}
    role_words = set()
    for k, _d, _n in sig_a[:8]:
        words = _PASCAL.findall(_stem_ext(k)[0]) or [_stem_ext(k)[0]]
        if words:
            role_words.add(words[-1])
    ent_roles: dict[str, set] = defaultdict(set)
    for p in paths:
        stem = _stem_ext(posixpath.basename(p))[0]
        words = _PASCAL.findall(stem)
        if len(words) >= 2 and words[-1] in role_words:
            ent_roles["".join(words[:-1])].add(words[-1])
    multi = {e: rs for e, rs in ent_roles.items() if len(rs) >= 2}
    sig_e = sorted(multi.items(), key=lambda kv: -len(kv[1]))

    print(f"\n===== {root}  ({len(files)} files) =====")
    print("A name-varying template (suffix: #dirs, #files):",
          [(k, f"{d}d/{n}f") for k, d, n in sig_a[:6]] or "(none)")
    print("B fixed-name convention (exact basename x #dirs):",
          sig_b[:8] or "(none)")
    print("C recurring DIR SHAPE (top, #dirs x roles):")
    if not sig_c:
        print("    (no dir shape recurs)")
    for shape, dirs in sig_c[:4]:
        print(f"    {len(dirs):2d} dirs  roles={sorted(shape)}")
        print(f"            e.g. {dirs[:3]}")
    print("E cross-layer STEM FAMILY (role vocab:", sorted(role_words), "):")
    if not sig_e:
        print("    (no stem spans >=2 roles)")
    else:
        print(f"    {len(sig_e)} entities span >=2 roles; fullest exemplars:")
        for ent, roles in sig_e[:5]:
            print(f"      {ent:22s} {sorted(roles)}")


def main(argv):
    if not argv:
        print("usage: explore_exemplar_signals.py <src-root>")
        return 2
    explore(Path(argv[0]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
