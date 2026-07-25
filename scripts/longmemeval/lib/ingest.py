"""Throwaway: RESUMABLE ingest of LongMemEval haystacks into a PERSISTENT menhir/Neo4j under
STABLE namespaces (lme-<question_id>), no per-item reset on success -- so recall-only A/B
(main vs frontier) can run against the pre-ingested graph without re-ingesting.

Resumability:
- An incremental manifest (results/lme-ingest/manifest.json) records each FULLY-ingested AND
  FULLY-ENRICHED item.
- On restart, items already in the manifest are SKIPPED.
- An item NOT in the manifest may have partial data from a prior crash, so its namespace is
  RESET (DELETE /api/namespace) before re-ingesting -- guarantees no duplicate episodes.
- Per-turn ingest has bounded retry/backoff; if it still fails the script exits non-zero and a
  re-run resumes from the manifest.

Enrichment completeness (why a per-item DRAIN exists):
- The HTTP ingest `wait=true` is best-effort with a 60s/episode cap, so slow episodes (which need
  up to MENHIR_MAX_LLM_CALLS_PER_JOB extraction calls) leave a PENDING/ENRICHING backlog behind a
  single background worker. Marking an item "done" the instant its last turn POST returns would
  record a HALF-ENRICHED namespace -- recall would then run against an incomplete graph.
- So after ingesting an item's turns we DRAIN: poll until menhir's queue_depth==0 (authoritative
  unprocessed-work count, from /api/stats) AND no episode is PENDING or ENRICHING (the two
  non-terminal lifecycle states, read from Neo4j) -- stable across two polls -- before writing the
  manifest. This makes "manifest done" mean "fully enriched", and keeps resume correct. (Gating on
  ENRICHING alone let the drain settle while a PENDING backlog the worker had not yet claimed still
  existed, which then slipped an unenriched namespace into scalar consolidation and aborted the run.)
- Benchmark mode disables the scheduler, so FAILED episodes are never auto-retried. After draining
  we run one best-effort FAILED-retry pass (force_reset_failed_episode + re-drain) to recover the
  episodes that hit the per-job LLM budget.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Derive real Windows paths from <repo>/scripts/longmemeval/lib/ingest.py.
# parents[3] is the repository root; the old parents[1] value silently placed the
# standalone default manifest under scripts/longmemeval instead of results/lme-ingest.
# Environment-provided manifest and fixture paths remain explicit overrides.
BENCH_ROOT = Path(__file__).resolve().parents[3]
if str(BENCH_ROOT) not in sys.path:
    sys.path.insert(0, str(BENCH_ROOT))
LIB_ROOT = Path(__file__).resolve().parent
if str(LIB_ROOT) not in sys.path:
    sys.path.insert(0, str(LIB_ROOT))

DEFAULT_MANIFEST = os.getenv(
    "LME_MANIFEST_PATH",
    str(BENCH_ROOT / "results" / "lme-ingest" / "manifest.json"),
)


import httpx  # noqa: E402
from archolith_bench.harness.longmemeval import LongMemEvalMemoryAdapter  # noqa: E402
from archolith_bench.harness.menhir_client import HttpMenhirClient  # noqa: E402

from claim_segmenter import (  # noqa: E402
    ClaimSegment,
    SegmentationMode,
    _heuristic_extract_claims,
    segmentation_mode as decide_segmentation,
)


def _heuristic_extract_claims_sync(content: str, role: str) -> list[ClaimSegment]:
    """Synchronous wrapper for Stage B heuristic claim extraction."""
    return _heuristic_extract_claims(content, role)

# Throwaway lme Neo4j (must match _lme_build_db.sh).
NEO4J_CONTAINER = os.getenv("LME_NEO4J_CONTAINER", "menhir-lme-neo4j")
NEO4J_PW = os.getenv("LME_NEO4J_PW", "lmedata123")
REQUIRE_TURN_EVIDENCE = os.getenv("LME_REQUIRE_TURN_EVIDENCE", "0").strip().lower() in {
    "1", "true", "yes", "on",
}

# Sentence splitting — long multi-topic messages bury factual claims in geographic
# noise, causing Graphiti's node resolution to collapse distinct entities (e.g.
# "the suburbs" into "Chicago").  Splitting isolates each claim so extraction
# sees one topic per episode.
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")
_SPLIT_MIN_LENGTH = int(os.getenv("LME_SPLIT_MIN_LENGTH", "100"))


def _split_sentences(text: str, min_length: int = _SPLIT_MIN_LENGTH) -> list[str]:
    """Split *text* on sentence boundaries when it exceeds *min_length* chars.

    Returns a list of non-empty stripped strings.  Short texts return as a
    single-element list so the caller can always iterate.
    """
    if len(text) <= min_length:
        return [text]
    parts = _SENTENCE_BOUNDARY.split(text)
    return [p.strip() for p in parts if p.strip()]


def _parse_lme_date(date_str: str | None) -> str | None:
    """Parse a LongMemEval haystack_date string to an ISO-8601 UTC string.

    LME format: "2023/07/14 (Fri) 08:30".  Returns None on any parse failure
    so callers fall back to menhir's default (ingestion time).
    """
    if not date_str:
        return None
    try:
        dt = datetime.strptime(date_str, "%Y/%m/%d (%a) %H:%M")
        return dt.replace(tzinfo=timezone.utc).isoformat()
    except (ValueError, TypeError):
        return None


def _ingest_turn(
    client: HttpMenhirClient,
    ns: str,
    role: str,
    content: str,
    *,
    tries: int = 4,
    occurred_at: str | None = None,
    session_id: str | None = None,
) -> None:
    """Ingest one turn with bounded exponential backoff on transient errors.

    For user turns, records :TurnEvidence first so the ``source="user"`` claim
    passes Menhir's admission gate (requires a grounding UUID).  Without it the
    gate downgrades the claim to ``agent_inference`` and writes a noisy
    admission-denial entity.

    Uses wait=False: the per-item drain is the real completeness guarantee,
    so we don't block per-turn.  This removes ~11k blocking round-trips and
    lets the single enrichment worker drain back-to-back with no idle gaps.
    """
    is_user = role.strip().lower() == "user"
    turn_evidence_uuid: str | None = None

    # Ground the user-tier claim by recording turn evidence first.
    if is_user:
        for attempt in range(tries):
            try:
                ev = client.record_turn_evidence(
                    ns,
                    content,
                    role="user",
                    session_id=session_id,
                )
                turn_evidence_uuid = ev.get("turn_id")
                break
            except (httpx.HTTPError,) as exc:
                if attempt == tries - 1:
                    if REQUIRE_TURN_EVIDENCE:
                        raise RuntimeError(
                            f"turn-evidence capture failed after {tries} attempts"
                        ) from exc
                    # Legacy compatibility for non-scalar diagnostic builds.
                    print(f"    turn-evidence failed after {tries} attempts: {exc.__class__.__name__}; "
                          "ingesting without grounding", flush=True)
                wait = 2 ** (attempt + 1)
                print(f"    turn-evidence retry {attempt+1}/{tries} after {exc.__class__.__name__} -> sleep {wait}s", flush=True)
                time.sleep(wait)

    for attempt in range(tries):
        try:
            client.ingest(
                ns,
                role,
                content,
                occurred_at=occurred_at,
                session_id=session_id,
                # A user's own utterance is external testimony -> "user" is a Guard-5 anchor kind,
                # so facts the user stated survive the EvidenceAnchorWarden. Assistant/system turns
                # stay unanchored (default "remote-api" -> agent_inference).
                source=("user" if is_user else None),
                turn_evidence_uuid=turn_evidence_uuid,
                wait=False,
            )
            return
        except (httpx.HTTPError,) as exc:
            if attempt == tries - 1:
                raise
            wait = 2 ** (attempt + 1)
            print(f"    ingest retry {attempt+1}/{tries} after {exc.__class__.__name__} -> sleep {wait}s", flush=True)
            time.sleep(wait)


def _cypher(query: str) -> list[list[str]]:
    """Run a read-only cypher query against the lme Neo4j via docker exec; return data rows
    (header dropped). Returns [] on any failure (docker missing / neo4j unreachable)."""
    try:
        proc = subprocess.run(
            ["docker", "exec", NEO4J_CONTAINER, "cypher-shell", "-u", "neo4j", "-p", NEO4J_PW,
             "--format", "plain", query],
            capture_output=True, text=True, timeout=300,
        )
    except Exception:
        return []
    if proc.returncode != 0:
        return []
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    rows = []
    for ln in lines[1:]:  # drop header
        rows.append([c.strip().strip('"') for c in ln.split(", ")])
    return rows


def _ns_state_counts(ns: str) -> dict[str, int]:
    """Per-namespace processing-state counts from Neo4j. PENDING and ENRICHING are the two
    non-terminal lifecycle states (in-flight); READY and FAILED are terminal (see menhir
    episode_lifecycle.mark_episode_ready/_failed). Episodic nodes with a NULL processing_state are
    graphiti-derived resolved nodes, not ingest episodes, and are deliberately excluded from the
    in-flight signal so the drain never waits on them forever."""
    rows = _cypher(
        f"MATCH (e:Episodic {{namespace:'{ns}'}}) RETURN "
        "sum(CASE WHEN e.processing_state='PENDING' THEN 1 ELSE 0 END) AS pending, "
        "sum(CASE WHEN e.processing_state='READY' THEN 1 ELSE 0 END) AS ready, "
        "sum(CASE WHEN e.processing_state='ENRICHING' THEN 1 ELSE 0 END) AS enriching, "
        "sum(CASE WHEN e.processing_state='FAILED' THEN 1 ELSE 0 END) AS failed, "
        "count(*) AS total;"
    )
    if not rows or len(rows[0]) < 5:
        return {"pending": -1, "ready": -1, "enriching": -1, "failed": -1, "total": -1}
    r = rows[0]
    return {"pending": int(r[0] or 0), "ready": int(r[1] or 0), "enriching": int(r[2] or 0),
            "failed": int(r[3] or 0), "total": int(r[4] or 0)}


def _cypher_count(query: str) -> int:
    rows = _cypher(query)
    if not rows or not rows[0]:
        return -1
    return int(rows[0][0] or 0)


def _scalar_counts(ns: str) -> dict[str, int]:
    """Return the materialization/provenance counts needed to trust a scalar snapshot."""
    return {
        "turn_evidence": _cypher_count(
            f"MATCH (t:TurnEvidence {{namespace:'{ns}'}}) RETURN count(t);"
        ),
        "typed_assertions": _cypher_count(
            f"MATCH (a:TypedAssertion {{namespace:'{ns}'}}) RETURN count(a);"
        ),
        "scalar_views": _cypher_count(
            f"MATCH (v:Entity {{group_id:'{ns}', view_kind:'scalar_state'}}) "
            "WHERE coalesce(v.view_current, true) RETURN count(v);"
        ),
        "user_founded_scalar_views": _cypher_count(
            f"MATCH (t:TurnEvidence {{namespace:'{ns}', declarant:'user'}})-[:FOUNDS]->"
            f"(a:TypedAssertion {{namespace:'{ns}'}})<-[:CURRENT_ANCHOR]-"
            f"(v:Entity {{group_id:'{ns}', view_kind:'scalar_state'}}) "
            "WHERE coalesce(v.view_current, true) RETURN count(DISTINCT v);"
        ),
    }


def _consolidate_scalar(
    admin: httpx.Client,
    menhir_url: str,
    namespace: str,
    *,
    k: int,
    call_budget: int,
) -> dict:
    response = admin.post(
        menhir_url.rstrip("/") + "/api/phase3/run",
        json={
            "namespace": namespace,
            "k": k,
            "source": "longmemeval-scalar-build",
            "call_budget": call_budget,
            "counter_state": False,
        },
        timeout=1800.0,
    )
    response.raise_for_status()
    result = response.json()
    if not result.get("scalar_enabled"):
        raise RuntimeError("Menhir did not enable scalar consolidation")
    if int(result.get("scalar_namespaces_processed", 0)) != 1:
        raise RuntimeError(f"scalar consolidation did not finish namespace {namespace}: {result}")
    # A scalar namespace can legitimately abstain from materializing an assertion, but it cannot
    # claim consolidation without exercising the k-sample perception boundary. This also catches
    # stale servers whose scheduler used to snapshot llm_calls before the scalar pass.
    if int(result.get("llm_calls", 0)) < k:
        raise RuntimeError(
            f"scalar consolidation did not exercise {k} LLM samples for {namespace}: {result}"
        )
    return result


def _failed_uuids(ns: str, limit: int = 2000) -> list[str]:
    rows = _cypher(
        f"MATCH (e:Episodic {{namespace:'{ns}'}}) WHERE e.processing_state='FAILED' "
        f"RETURN e.uuid AS uuid LIMIT {limit};"
    )
    return [r[0] for r in rows if r and r[0]]


def _queue_depth(admin: httpx.Client, menhir_url: str) -> int:
    """menhir's authoritative count of unprocessed enrichment work (global; == current
    namespace because items are ingested one at a time). -1 if unavailable."""
    try:
        resp = admin.get(menhir_url.rstrip("/") + "/api/stats")
        resp.raise_for_status()
        return int(resp.json().get("queue_depth", -1))
    except Exception:
        return -1


def _backend(admin: httpx.Client, menhir_url: str, op: str, body: dict | None = None):
    """Invoke an internal backend operation; raises on HTTP error."""
    url = menhir_url.rstrip("/") + "/api/internal/backend/" + op
    resp = admin.post(url, json=(body or {}))
    resp.raise_for_status()
    return resp.json()


def _drain(ns: str, admin: httpx.Client, menhir_url: str, *,
           idle_polls: int = 2, poll_s: float = 2.0, timeout_s: float = 1800.0) -> dict:
    """Block until enrichment for the current namespace is fully settled: queue_depth==0 AND no
    episode in a non-terminal lifecycle state (PENDING or ENRICHING), stable for `idle_polls`
    consecutive checks (or `timeout_s` elapses). Returns the last state-count snapshot (with
    timed_out flag).

    PENDING is gated on, not just ENRICHING: an episode the single background worker has not yet
    claimed sits in PENDING with enriching==0, so gating on ENRICHING alone let the drain settle
    while an unenriched backlog remained -- that empty namespace then reached scalar consolidation,
    which hard-fails when phase3 finds nothing dirty and aborts the whole run. Waiting on PENDING
    closes the hole; `timeout_s` still bounds a namespace whose backlog genuinely never clears."""
    t0 = time.time()
    settled = 0
    last = {"pending": -1, "ready": -1, "enriching": -1, "failed": -1, "total": -1}
    while time.time() - t0 < timeout_s:
        qd = _queue_depth(admin, menhir_url)
        last = _ns_state_counts(ns)
        # pending/enriching==-1 means cypher timed out / Neo4j temporarily unreachable. Treat
        # unknown as in-flight so we keep polling rather than settling early; only settle when
        # cypher confirms both non-terminal counts are 0.
        pending = last["pending"] if last["pending"] >= 0 else 1
        enriching = last["enriching"] if last["enriching"] >= 0 else 1
        in_flight = pending + enriching
        if qd == 0 and in_flight == 0:
            settled += 1
            if settled >= idle_polls:
                last["timed_out"] = False
                return last
        else:
            settled = 0
        time.sleep(poll_s)
    last["timed_out"] = True
    return last


def _retry_failed(ns: str, admin: httpx.Client, menhir_url: str) -> int:
    """Best-effort: re-enqueue FAILED episodes in the namespace (the scheduler that normally
    retries them is off in benchmark mode). Returns the number re-enqueued."""
    uuids = _failed_uuids(ns)
    if not uuids:
        return 0
    requeued = 0
    for u in uuids:
        try:
            if _backend(admin, menhir_url, "force_reset_failed_episode", {"episode_uuid": u}):
                requeued += 1
        except Exception:
            pass  # internal endpoint unavailable / auth -> leave FAILED, report residual
    return requeued


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=500)
    ap.add_argument("--menhir-url", default="http://localhost:8102")
    ap.add_argument("--manifest", default=DEFAULT_MANIFEST)
    ap.add_argument(
        "--fixture",
        default=os.getenv("LME_FIXTURE_PATH"),
        help="offline LongMemEval JSON array; defaults to LME_FIXTURE_PATH when set",
    )
    ap.add_argument(
        "--namespace-prefix",
        default=os.getenv("LME_NS_PREFIX", "lme-"),
        help="namespace prefix for ingested items (default: LME_NS_PREFIX or lme-)",
    )
    ap.add_argument("--drain-timeout", type=float, default=1800.0,
                    help="max seconds to wait for an item's enrichment to settle")
    ap.add_argument("--consolidate-scalar", action="store_true",
                    help="run scalar-only Phase 3 consolidation before manifesting each namespace")
    ap.add_argument("--consolidation-k", type=int, default=3)
    ap.add_argument("--consolidation-call-budget", type=int, default=50)
    ap.add_argument(
        "--segmentation",
        choices=["none", "sentence", "user-sentence", "adaptive"],
        default=os.getenv("LME_SEGMENTATION", "sentence"),
        help=(
            "Turn segmentation strategy: "
            "'none' = no splitting (arm A), "
            "'sentence' = blind sentence split (arm B, default/legacy), "
            "'user-sentence' = split only user turns (arm C), "
            "'adaptive' = claim-aware segmentation (arm D)"
        ),
    )
    return ap.parse_args(argv)

def _load_items(
    adapter: LongMemEvalMemoryAdapter,
    *,
    limit: int,
    fixture_path: str | None,
) -> list[dict]:
    items = adapter.load_items(limit=limit, fixture_path=fixture_path)
    if fixture_path and not items:
        raise ValueError(f"LongMemEval fixture is empty: {fixture_path}")
    return items


def _namespace(question_id: str, prefix: str) -> str:
    clean_prefix = prefix.strip()
    if not clean_prefix:
        raise ValueError("namespace prefix must not be empty")
    return f"{clean_prefix}{question_id}"


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    adapter = LongMemEvalMemoryAdapter()
    source = (
        f"fixture={args.fixture}"
        if args.fixture
        else f"variant={os.getenv('LONGMEMEVAL_VARIANT', 's')}"
    )
    print(f"loading LongMemEval items (limit={args.limit}, {source})...", flush=True)
    items = _load_items(adapter, limit=args.limit, fixture_path=args.fixture)
    print(f"loaded {len(items)} items", flush=True)

    manifest_path = Path(args.manifest)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest: list[dict] = []
    done_ids: set[str] = set()
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        done_ids = {m["question_id"] for m in manifest}
        print(f"RESUME: {len(done_ids)} items already ingested (skipping them)", flush=True)

    client = HttpMenhirClient(args.menhir_url)
    admin = httpx.Client(timeout=120.0)
    t_all = time.time()
    remaining = [it for it in items if str(it.get("question_id") or "") not in done_ids]
    print(f"to ingest this run: {len(remaining)} items", flush=True)

    for n, item in enumerate(remaining):
        qid = str(item.get("question_id") or f"lme-{n}")
        ns = _namespace(qid, args.namespace_prefix)
        # Item not in manifest -> may be partially ingested from a prior crash; reset clean.
        try:
            client.reset(ns)
        except Exception:
            pass
        turns = 0
        t0 = time.time()
        haystack_dates = item.get("haystack_dates") or []
        haystack_session_ids = item.get("haystack_session_ids") or []
        for s_idx, session in enumerate(adapter.sessions(item)):
            s_date = haystack_dates[s_idx] if s_idx < len(haystack_dates) else None
            s_id = haystack_session_ids[s_idx] if s_idx < len(haystack_session_ids) else None
            occurred_at = _parse_lme_date(s_date)
            # Namespace-qualify the session id. The LongMemEval fixture reuses identical
            # haystack_session_ids across temporal-variant question pairs (e.g. 89941a93/89941a94,
            # 07741c44/07741c45); ingesting each item into its own namespace but sharing the raw
            # session id lets Graphiti's entity resolution dedup the second item's nodes against the
            # first item's already-resolved (cross-namespace) nodes, which menhir's namespace filter
            # then drops -- leaving dangling edge endpoints, orphan-pruned nodes, and a collapsed
            # (zero TurnEvidence) extraction. Qualifying by namespace guarantees per-item isolation.
            session_id = f"{ns}-{s_id}" if s_id else f"{ns}-s{s_idx}"
            for turn in session:
                content = turn.get("content", "")
                if not content:
                    continue
                role = turn.get("role", "user")
                seg = args.segmentation

                if seg == "none":
                    # Arm A: no splitting at all
                    _ingest_turn(client, ns, role, content,
                                 occurred_at=occurred_at, session_id=session_id)
                    turns += 1

                elif seg == "sentence":
                    # Arm B: legacy blind sentence split
                    for sentence in _split_sentences(content):
                        _ingest_turn(client, ns, role, sentence,
                                     occurred_at=occurred_at, session_id=session_id)
                        turns += 1

                elif seg == "user-sentence":
                    # Arm C: split only user messages, assistant whole
                    if role.strip().lower() == "user":
                        for sentence in _split_sentences(content):
                            _ingest_turn(client, ns, role, sentence,
                                         occurred_at=occurred_at, session_id=session_id)
                            turns += 1
                    else:
                        _ingest_turn(client, ns, role, content,
                                     occurred_at=occurred_at, session_id=session_id)
                        turns += 1

                elif seg == "adaptive":
                    # Arm D: claim-aware segmentation
                    mode = decide_segmentation(role, content)

                    if mode == SegmentationMode.SKIP:
                        continue

                    elif mode == SegmentationMode.CONTEXT_ONLY:
                        # Ingest as context but don't extract — use wait=False
                        # and mark as assistant/low-priority so extraction
                        # treats it as background context
                        _ingest_turn(client, ns, role, content,
                                     occurred_at=occurred_at, session_id=session_id)
                        turns += 1

                    elif mode == SegmentationMode.EXTRACT_WHOLE:
                        _ingest_turn(client, ns, role, content,
                                     occurred_at=occurred_at, session_id=session_id)
                        turns += 1

                    elif mode == SegmentationMode.SEGMENT_CLAIMS:
                        # Ingest the original turn first (preserves context)
                        _ingest_turn(client, ns, role, content,
                                     occurred_at=occurred_at, session_id=session_id)
                        turns += 1
                        # Then extract and ingest individual claim segments
                        claims = _heuristic_extract_claims_sync(content, role)
                        for claim in claims:
                            _ingest_turn(client, ns, role, claim.text,
                                         occurred_at=occurred_at, session_id=session_id)
                            turns += 1

                else:
                    # Fallback: no splitting
                    _ingest_turn(client, ns, role, content,
                                 occurred_at=occurred_at, session_id=session_id)
                    turns += 1

        # DRAIN: wait for this item's enrichment to fully settle before recording it as done,
        # so "manifest done" == "fully enriched" (recall A/B then sees a complete graph).
        drained = _drain(ns, admin, args.menhir_url, timeout_s=args.drain_timeout)
        # Best-effort FAILED-retry (scheduler is off in benchmark mode), then re-drain once.
        requeued = 0
        if drained.get("failed", 0) > 0:
            requeued = _retry_failed(ns, admin, args.menhir_url)
            if requeued:
                drained = _drain(ns, admin, args.menhir_url, timeout_s=args.drain_timeout)

        scalar_result: dict = {}
        scalar_counts: dict[str, int] = {}
        if args.consolidate_scalar:
            scalar_result = _consolidate_scalar(
                admin,
                args.menhir_url,
                ns,
                k=args.consolidation_k,
                call_budget=args.consolidation_call_budget,
            )
            scalar_counts = _scalar_counts(ns)
            if scalar_counts["turn_evidence"] <= 0:
                raise RuntimeError(f"no TurnEvidence captured for scalar namespace {ns}")

        manifest.append({
            "question_id": qid, "namespace": ns,
            "fixture": str(Path(args.fixture).resolve()) if args.fixture else None,
            "question": adapter.question(item), "answer": str(item.get("answer", "")),
            "question_type": item.get("question_type"), "turns": turns,
            "episodes": drained.get("total"), "ready": drained.get("ready"),
            "failed_remaining": drained.get("failed"), "failed_requeued": requeued,
            "drain_timed_out": drained.get("timed_out", False),
            "scalar_consolidated": bool(
                args.consolidate_scalar
                and int(scalar_result.get("scalar_namespaces_processed", 0)) == 1
                and int(scalar_result.get("llm_calls", 0)) >= args.consolidation_k
            ),
            "scalar_llm_calls": int(scalar_result.get("llm_calls", 0)),
            "scalar_states_written": int(scalar_result.get("scalar_states_written", 0)),
            **scalar_counts,
        })
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        elapsed = time.time() - t_all
        rate = (n + 1) / elapsed if elapsed else 0
        eta = (len(remaining) - (n + 1)) / rate if rate else 0
        flag = " DRAIN-TIMEOUT" if drained.get("timed_out") else ""
        print(f"[{len(done_ids)+n+1}/{len(items)}] {qid} ns={ns} turns={turns} "
              f"episodes={drained.get('total')} ready={drained.get('ready')} "
              f"failed={drained.get('failed')} requeued={requeued} "
              f"item={time.time()-t0:.0f}s total={elapsed:.0f}s eta={eta/3600:.1f}h{flag}", flush=True)

    print(f"\nDONE: manifest has {len(manifest)}/{len(items)} items -> {args.manifest}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
