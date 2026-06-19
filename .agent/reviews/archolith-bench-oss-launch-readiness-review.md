# archolith-bench OSS Launch Readiness Review

Review of the repo at `C:\Users\thron\IdeaProjects\projects\archolith\archolith-bench` as of
commit `ea1f281` (HEAD), with an uncommitted `README.md` edit in the working tree. Reviewed
against current files only — no prior notes or memory.

The goal: can a stranger clone, install, run a meaningful benchmark, understand the results,
and trust the headline numbers?

---

## Findings

### Finding 1 — Blocker: install fails for any stranger; both runtime deps are unpublished

- **Severity:** Blocker
- **Location:**
  - `pyproject.toml:25-27` — `dependencies = ["httpx>=0.27", "python-dotenv>=1.0", "archolith-filter", "archolith-audit"]`
  - Code imports: `archolith_bench/suites/filter.py:15` (`from archolith_filter import ...`),
    `archolith_bench/suites/audit.py:14` (`from archolith_mcp_audit.comparator import ...`)
- **Issue:** The package's two non-trivial dependencies — `archolith-filter` and `archolith-audit`
  — are **not published to PyPI**. Verified live:
  `pip download archolith-filter` → `ERROR: Could not find a version that satisfies the requirement
  archolith-filter`; same for `archolith-audit`. The README Quick Start (`README.md:29`) tells a
  stranger to run `pip install -e .`, which will fail at dependency resolution. There is no
  documented fallback (git URLs, monorepo install order, vendoring, or `--no-deps` instructions).
- **Impact:** Hard launch blocker. The primary documented install path does not work for anyone
  outside the maintainer's machine. Filter and audit suites — the only two suites that run without
  a live proxy/API key — both `ImportError` without these.
- **Evidence:**
  - `pip show archolith-filter` resolves only because it is installed editable from
    `C:\Users\thron\IdeaProjects\projects\archolith\archolith-filter` (local monorepo), not from a
    public index.
  - `projects/archolith/archolith-filter/pyproject.toml` sets `Repository = github.com/archolith/archolith-filter`
    but the package has no `dist/` and no PyPI presence.
  - README.md "Quick Start" offers no install alternative for the missing deps.
- **Suggested fix:** Before launch, either (a) publish both deps to PyPI, or (b) document a
  monorepo/git install path in the README (e.g. `pip install git+https://.../archolith-filter.git`
  or clone-and-`pip install -e` for all three repos in order), or (c) vendor the two deps into this
  repo. Pick one and verify `pip install -e .` succeeds in a clean venv from a fresh clone.
- **Confidence:** 100% — verified against the live PyPI index and the local install metadata.

---

### Finding 2 — Blocker: the headline 58.6% proxy savings is internally inconsistent and overstates real savings

- **Severity:** Blocker (benchmark integrity / misleading public claim)
- **Location:**
  - `README.md:11` — "Proxy token savings | **58.6%** | 10-turn code review, DeepSeek upstream"
  - `HEADLINE-NUMBERS.md:31-32` — canonical claim, commit `5112334`
  - `archolith_bench/suites/proxy.py:396-443` — the ratio computation
  - `results/benchmark_code_review_proxy_only_4000b.json` and `..._proxy_only_15000b.json` (local only)
- **Issue:** The published 58.6% is **not** (direct − arm)/direct. It is computed at
  `proxy.py:443` as `total_savings_tokens / total_direct_input_tokens`, where
  `total_savings_tokens` (line 398) sums the per-turn `trace.savings_tokens` reported by the proxy.
  That proxy-internal "savings" figure measures *curation* (raw context it would have sent vs the
  curated subset), **not** the tokens actually billed upstream. The result: the headline ratio can
  be large and positive even when the arm consumed *more* upstream tokens than the direct baseline.
- **Impact:** The flagship number does not measure what the README implies (your actual token bill
  drops ~59%). A skeptical user who recomputes from the same result files gets a very different
  number and will reasonably conclude the claim is fabricated. Concretely, recomputed from the
  bundled result JSONs against the published 58.6%:

  | Arm / budget | direct_in | arm_in (upstream) | reported savings | REAL (direct−arm)/direct |
  |---|---|---|---|---|
  | proxy_only @ 15K | 108,516 | 80,520 | **58.6%** | **25.8%** |
  | proxy_only @ 4K  | 108,516 | 91,701 | **58.6%** | **15.5%** |
  | proxy_plus_filter @ 15K | 108,376 | 111,021 | **58.6%** | **−2.4%** (arm used MORE) |

- **Evidence:** Loaded each JSON with Python; `summary.overall_savings_ratio` vs
  `(total_direct_input_tokens − total_proxy_input_tokens)/total_direct_input_tokens`. The 4K and
  15K rows report the *same* 58.6% despite consuming different amounts, and the proxy_plus_filter
  row reports 58.6% while the arm used more tokens than direct.
- **Suggested fix:** Define one unambiguous savings metric and make the headline use it. Either
  (a) re-state the headline as upstream-vs-upstream (`(direct_in − arm_in)/direct_in`), which yields
  15–26% here, or (b) if the proxy-internal curation number is the intended metric, rename it
  ("curated-context reduction") and never present it alongside direct/arm token columns without a
  methodology note. As written, the headline table is not reproducible from the bundled results.
- **Confidence:** 100% — arithmetic re-verified against three result files.

---

### Finding 3 — Blocker: one stored result JSON contradicts its own per-turn data (summary drift)

- **Severity:** Blocker (reproducibility / result integrity)
- **Location:** `results/benchmark_code_review_proxy_plus_filter_15000b.json` (local only, gitignored)
- **Issue:** In this file, **every** turn's `trace.savings_tokens` is `0`, but `summary.total_savings_tokens`
  is `63,579` and `summary.overall_savings_ratio` is `0.5867`. Per `proxy.py:398`, the summary is the
  sum of per-turn `savings_tokens`, so a self-consistent file would have `total_savings_tokens = 0`.
  The summary block was evidently carried over from a different (proxy_only-shaped) run. By contrast,
  the two `proxy_only` files are internally consistent (per-turn sum = 63,579 = summary).
- **Impact:** Anyone auditing the headline from the result files finds the proxy_plus_filter artifact
  self-contradictory, which independently undermines Finding 2 and erodes trust in all stored results.
  Because `results/` is gitignored (Finding 4), this file won't ship — but it is the *source* the
  headline was derived from, and the same drift can recur on any future run with no guardrail.
- **Evidence:** `python -c` over the file: `sum(t['trace']['savings_tokens'] for t in turns) == 0`,
  while `summary['total_savings_tokens'] == 63579`.
- **Suggested fix:** Add a consistency check that the persisted summary equals a fresh recomputation
  from the turns array (cheap unit test on `save_results` output), and regenerate/regit the canonical
  result files from a single clean run before publishing.
- **Confidence:** 100%.

---

### Finding 4 — High: `results/`, `logs/`, and the entire result/transcript tree are gitignored — nothing ships

- **Severity:** High (reproducibility / "source for claims")
- **Location:** `.gitignore:1` (`results/`), `.gitignore:9` (`logs/`)
- **Issue:** All `results/benchmark_*.json`, `results/transcripts/*.md`, `results/filter_results.json`,
  `results/audit_comparison.json`, and the `logs/` files are local-only. `git ls-files results/` returns
  zero files. HEADLINE-NUMBERS.md anchors its numbers to commit `5112334`/`18057ca` and to specific
  result artifacts, but those artifacts are not in the repo a stranger clones.
- **Impact:** A stranger following "reproduction instructions" cannot find the source data behind any
  headline, and there is no committed evidence the published numbers were ever produced by this code.
  The filter corpus and audit fixtures DO ship (tracked), so the filter/audit numbers are reproducible
  in principle — but the proxy headline is not, because neither the code-derived result nor a tracked
  artifact exists to back it.
- **Evidence:** `git ls-files results/` → 0; `git ls-files` total includes `corpora/`, `fixtures/`,
  `scenarios/` but no `results/` or `logs/`.
- **Suggested fix:** Commit at least the canonical headline-backing result files (or a
  `results/published/` subset with a README stating provenance, commit, and run command). Continue to
  gitignore ad-hoc reruns. Alternatively, move provenance artifacts to a tracked `docs/results/` dir.
- **Confidence:** 100%.

---

### Finding 5 — High: audit "after" fixture is a projected assumption, not a measurement

- **Severity:** High (claim integrity, even though labeled)
- **Location:**
  - `fixtures/audit_after.json:2-3` — `"_source": "Projected from live session with archolith-rtk
    filtering applied per-server"`, `"_method": "Applied category-specific filter savings: JSON/MCP 75%,
    text/artifacts 30%, build 40%"`
  - `BENCHMARKS.md:26-41` and `HEADLINE-NUMBERS.md:42` — 71.5% waste reduction / 43.9% token reduction
- **Issue:** The "after" side of the audit comparison is the "before" numbers reduced by *assumed*
  per-category percentages (75/30/40), not a measured post-filter audit run. So the headline 71.5%
  waste reduction is, in part, the assumed filter rates feeding back out. It is honestly labeled as
  fixture data in BENCHMARKS.md (a note is emitted) and HEADLINE-NUMBERS.md tags it
  `[FIXTURE — not for copy until live audit run confirms]` — but the table still presents a clean
  per-server "improved" result that reads like data.
- **Impact:** A reader scanning the audit table sees authoritative-looking per-server deltas; the
  circular projection basis is easy to miss. Combined with Finding 4 (no live result ships), the only
  audit "result" in the repo is a self-referential projection.
- **Evidence:** `audit_after.json` `_method` field; re-derived both sides from the fixtures:
  before_waste=116,700, after_waste=33,200, reduction=83,500 (71.55%) — matches, confirming the
  after-side was constructed to hit the category rates.
- **Suggested fix:** Either run and ship one real before/after audit pair before launch, or make the
  fixture's projected nature unmissable in the table itself (e.g. a "PROJECTION" badge on the audit
  row, not only a preamble note). Keep the HEADLINE rule that this never becomes a marketing number.
- **Confidence:** 100%.

---

### Finding 6 — High: `pytest` collection errors from a stray experiment test that imports an absent module

- **Severity:** High (first-run contributor experience / CI)
- **Location:** `experiments/context-quality/task-microtemplate/tests/test_microtemplate.py:8`
  (`from microtemplate import render`); no `[tool.pytest.ini_options]` in `pyproject.toml`
- **Issue:** Running `pytest` from the repo root fails during collection:
  `ModuleNotFoundError: No module named 'microtemplate'` → `Interrupted: 1 error during collection`.
  The `experiments/` tree (1,206 tracked files, including `task-microtemplate/`) is committed but not
  excluded from test discovery, and there is no `testpaths`/`norecursedirs` config.
- **Impact:** A contributor's first `pytest` is red for a reason unrelated to the package. CI would
  fail identically. The package's own 6 tests in `tests/` never run because collection aborts first.
- **Evidence:** `python -m pytest -q` from repo root → collection error as above; `grep pytest
  pyproject.toml` returns nothing.
- **Suggested fix:** Add `[tool.pytest.ini_options]` with `testpaths = ["tests"]` (and/or
  `norecursedirs = ["experiments", ".benchmarks"]`), or move the stray experiment test out of the
  committed tree. Verify `pytest` is green from a clean clone.
- **Confidence:** 100%.

---

### Finding 7 — High: real DeepSeek API key present in the local `.env`

- **Severity:** High (security / trust), mitigated by not being committed
- **Location:** `.env` (on disk, gitignored via `.gitignore:3`)
- **Issue:** `.env` contains a real-looking key `sk-d17b…4969`. It is correctly gitignored and
  `git ls-files --error-unmatch .env` confirms it is NOT tracked. The risk is operational, not a
  repo leak: the key is committed to the maintainer's disk in a file whose template (`.env.example`)
  invites copying, and a future `git add -f` or bundle could expose it.
- **Impact:** No current leak to clones, but a single mistake publishes a live DeepSeek key.
- **Evidence:** `.env` contents (masked) show `UPSTREAM_API_KEY=sk-d17b***4969`; `.gitignore:3` lists
  `.env`; `git ls-files` does not include it.
- **Suggested fix:** Rotate the key before launch regardless, and consider a pre-commit hook that
  blocks `sk-` patterns. Keep `.env` gitignored (already is).
- **Confidence:** 100% (key format is consistent with a real DeepSeek key; treat as live until rotated).

---

### Finding 8 — Polish: pyproject vs README disagree on the repo/org URL

- **Severity:** Polish
- **Location:** `pyproject.toml:33-34` (`github.com/archolith/archolith-bench`) vs
  `README.md:3` (`github.com/ctharvey/archolith`)
- **Issue:** Two different GitHub orgs/usernames (`archolith` vs `ctharvey`) across the package
  metadata and README. Neither URL was verified to resolve.
- **Impact:** PyPI "Homepage"/"Issues" links may 404; README link may point at a different scope.
  First impression of sloppiness for an OSS launch.
- **Evidence:** grep results above.
- **Suggested fix:** Pick the canonical public URL, set it consistently in `pyproject.toml` and
  README, and verify both resolve before publish.
- **Confidence:** 100%.

---

### Finding 9 — Polish: README default env values disagree with `.env.example` and with how runs were actually done

- **Severity:** Polish
- **Location:** `README.md:57-59` (defaults `localhost:9800/v1`, `integrate.api.nvidia.com`, `gpt-4o-mini`);
  `.env.example:8-13` (`PROXY_URL=localhost:9801/v1`, `api.deepseek.com`, `deepseek-chat`);
  on-disk `.env` (`PROXY_PORT=9800`, `api.deepseek.com`, `deepseek-chat`)
- **Issue:** Three sources, three stories. The README's NVIDIA upstream default contradicts the
  "DeepSeek upstream" headline and every actual run; `.env.example`'s `9801` port contradicts the
  code default `9800` (`api.py:14`). The README does document the `report` subcommand nowhere.
- **Impact:** A stranger copying `.env.example` lands on a different port than the code default and
  the README. Confusing first run; looks unvetted.
- **Evidence:** diffs of the three sources as above; `api.py:14-18` defaults.
- **Suggested fix:** Align all three to one set of defaults; if runs are DeepSeek-based, make the
  documented default `api.deepseek.com`/`deepseek-chat` and port `9800`. Add the `report` subcommand
  to the README Suites table.
- **Confidence:** 100%.

---

### Finding 10 — Polish: two different "filter savings" numbers in published docs (49.5% vs 50.0%)

- **Severity:** Polish
- **Location:** `HEADLINE-NUMBERS.md:37` (49.5%) vs `README.md:12` (50.0%)
- **Issue:** README rounds 49.5% to "50.0%" for the headline; HEADLINE-NUMBERS keeps 49.5% and notes
  "site rounds to 50%". A stranger cross-checking sees two numbers.
- **Impact:** Minor trust friction; the rounding is disclosed in HEADLINE-NUMBERS but not in README.
- **Evidence:** the two cited lines.
- **Suggested fix:** Use one number everywhere, or add a one-line "(49.5% rounded)" note in README.
- **Confidence:** 100%.

---

### Finding 11 — Polish: `HEADLINE-NUMBERS.md` waste denominator typo (116,900 vs 116,700)

- **Severity:** Polish / Low-hanging fruit
- **Location:** `HEADLINE-NUMBERS.md:42` — "83,500 of 116,900 waste tokens"
- **Issue:** The actual `before_total_waste` summed from `fixtures/audit_before.json` is **116,700**
  (not 116,900). The 83,500 reduction and 71.5% are correct against 116,700; the denominator is off
  by 200.
- **Impact:** A trivially checkable arithmetic error in the "canonical source of truth" file.
- **Evidence:** `sum(f['tokens_wasted'] for s in before['servers'].values() for f in s['findings'])`
  = 116,700.
- **Suggested fix:** Correct 116,900 → 116,700.
- **Confidence:** 100%.

---

### Finding 12 — Polish: `report` subcommand never emits a Stack section, yet README advertises `stack`

- **Severity:** Polish
- **Location:** `archolith_bench/core/report.py:209-211` (Stack section is hardcoded
  "*Pending live-proxy run…*"); `README.md:24` advertises a `stack` suite
- **Issue:** `write_benchmarks_md` has no branch that reads stack output — it always prints "Pending".
  The `stack` suite (`suites/stack.py`) writes per-arm benchmark files but nothing the report wires
  into a four-way table, so `archolith-bench report` will always show Stack as pending even after a
  stack run.
- **Impact:** "Run `archolith-bench stack --all` to generate" in BENCHMARKS.md is misleading — the
  report won't surface it.
- **Evidence:** `report.py:209-211` unconditional pending string; no `stack_results` glob in the file.
- **Suggested fix:** Either wire stack output into `write_benchmarks_md`, or mark the Stack section
  as a roadmap item in the README rather than a runnable suite with a generated report.
- **Confidence:** 95% (did not execute a live stack run to confirm, but the code path has no
  alternative branch).

---

## Open Questions

1. **Is there a public GitHub home for `archolith-bench` at all?** Neither `github.com/ctharvey/archolith`
   nor `github.com/archolith/archolith-bench` was fetched; the maintainer should confirm which
   (if either) exists and is the launch target. Affects Finding 8.
2. **Is the proxy-internal "savings_tokens" the intended headline metric, or is upstream-vs-upstream
   the intended one?** Finding 2's fix depends on this product decision; the repo currently presents
   one as if it were the other. Maintainer input needed.
3. **Will `archolith-filter` / `archolith-audit` be published to PyPI, or is this a monorepo-only
   release?** Determines the fix shape for Finding 1.
4. **License inconsistency between sibling packages:** `archolith-audit`'s own pyproject declares
   `MIT` (`pip show` shows `License-Expression: MIT`) while `archolith-bench` and `archolith-filter`
   are PolyForm Noncommercial. Not verified whether the audit repo's LICENSE file actually matches —
   worth confirming the license story is coherent across the family before public launch.

## What Was Checked

**Files read in full:** `README.md`, `pyproject.toml`, `BENCHMARKS.md`, `HEADLINE-NUMBERS.md`,
`CLA.md`, `CONTRIBUTING.md`, `.env.example`, `.gitignore`, `.gitattributes`, `LICENSE` (header),
`archolith_bench/__init__.py`, `__main__.py`, `cli.py`, `arms.py`, `core/api.py`, `core/metrics.py`,
`core/report.py`, `suites/proxy.py`, `suites/filter.py`, `suites/audit.py`, all 6 `tests/*.py`,
`fixtures/audit_before.json`, `fixtures/audit_after.json`.

**Code/data executed (read-only):** loaded `results/benchmark_code_review_{direct,proxy_only,proxy_plus_filter}_{4000,15000}b.json`
and recomputed savings ratios and per-turn `savings_tokens` sums; summed waste tokens from both
audit fixtures; ran `pip download`/`pip show` for `archolith-filter` and `archolith-audit` against
the live index; ran `python -m pytest -q` from the repo root (collection error); `git ls-files`
counts for `results/`, `logs/`, `experiments/`; `git log --oneline -20`; verified referenced
commits `5112334` and `18057ca` resolve; inspected `git show --stat` for both.

**Counts proven:** 1,206 tracked files under `experiments/` (1,184 under `context-quality`,
22 under `curator-worker-gate`); 6 test files in `tests/`; 12 corpus samples; 6 scenarios; 2 audit
fixtures; 0 tracked `results/` files.

**Not executed / skipped (would need live infra or publish):** no live proxy run (proxy suite needs
a running archolith proxy + API key); no live `stack` run (same reason); did not fetch the two
GitHub URLs to confirm they resolve; did not attempt a clean-venv `pip install -e .` (Finding 1 is
already proven by the PyPI lookup); did not open the audit repo's LICENSE file (Open Question 4).

## Launch Recommendation

**Do not launch until Blockers are fixed.**

- Findings 1–3 are genuine launch blockers: the documented install path fails for any stranger
  (Finding 1), and the single most prominent public number is both internally inconsistent
  (Finding 2) and backed by a self-contradictory result artifact (Finding 3).
- Finding 2 in particular is the kind of discrepancy a hostile or careful reader will catch within
  a day of launch and publicize; it should be resolved (re-define the metric, re-run, or re-label)
  before any marketing copy goes out.
- Finding 4–7 are High but tractable in a pre-launch afternoon: ship canonical result artifacts,
  run or clearly badge one real audit, add a `testpaths` config, and rotate the on-disk key.
- Findings 8–12 are polish/low-hanging fruit and can ride the first post-launch patch, though
  Finding 8 (broken Homepage/Issues URLs on PyPI) should be fixed in the same commit as the publish.
- The repo's *code* quality and CLA/license posture are solid; the blockers are all about claims,
  reproducibility, and the install/run path — exactly the surfaces an OSS launch is judged on.

## Review Confidence

**93 / 100.** Every finding is backed by current-file evidence that I re-executed (result-file
arithmetic, `pip download`, `pytest`, `git ls-files`). What limits confidence: (a) I could not run
the live proxy/stack suites to confirm Finding 12's "Stack never reports" end-to-end (95% from code
reading only); (b) I did not fetch the two candidate GitHub URLs, so Finding 8's "they disagree" is
certain but "neither resolves" is unverified; (c) Finding 7 assumes the on-disk key is live — it
should be rotated regardless. No finding relies on memory, prior notes, or unverified assumptions.
