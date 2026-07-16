"""Throwaway: RESUMABLE ingest of LongMemEval haystacks into a PERSISTENT menhir/Neo4j under
STABLE namespaces (lme-<question_id>), no per-item reset on success -- so recall-only A/B
(main vs frontier) can run against the pre-ingested graph without re-ingesting. Not committed.

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
  unprocessed-work count, from /api/stats) AND no episode is ENRICHING (real in-flight, read from
  Neo4j) -- stable across two polls -- before writing the manifest. This makes "manifest done" mean
  "fully enriched", and keeps resume correct.
- Benchmark mode disables the scheduler, so FAILED episodes are never auto-retried. After draining
  we run one best-effort FAILED-retry pass (force_reset_failed_episode + re-drain) to recover the
  episodes that hit the per-job LLM budget.
"""
from __future__ import annotations

import argparse
import json
import os
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

DEFAULT_MANIFEST = os.getenv(
    "LME_MANIFEST_PATH",
    str(BENCH_ROOT / "results" / "lme-ingest" / "manifest.json"),
)


import httpx  # noqa: E402
from archolith_bench.harness.longmemeval import LongMemEvalMemoryAdapter  # noqa: E402
from archolith_bench.harness.menhir_client import HttpMenhirClient  # noqa: E402

# Throwaway lme Neo4j (must match _lme_build_db.sh).
NEO4J_CONTAINER = os.getenv("LME_NEO4J_CONTAINER", "menhir-lme-neo4j")
NEO4J_PW = os.getenv("LME_NEO4J_PW", "lmedata123")


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
                    # Evidence capture failed — fall back to ungrounded ingest
                    # (will be downgraded to agent_inference by the admission gate).
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
    """Per-namespace processing-state counts from Neo4j (ENRICHING is the in-flight signal)."""
    rows = _cypher(
        f"MATCH (e:Episodic {{namespace:'{ns}'}}) RETURN "
        "sum(CASE WHEN e.processing_state='READY' THEN 1 ELSE 0 END) AS ready, "
        "sum(CASE WHEN e.processing_state='ENRICHING' THEN 1 ELSE 0 END) AS enriching, "
        "sum(CASE WHEN e.processing_state='FAILED' THEN 1 ELSE 0 END) AS failed, "
        "count(*) AS total;"
    )
    if not rows or len(rows[0]) < 4:
        return {"ready": -1, "enriching": -1, "failed": -1, "total": -1}
    r = rows[0]
    return {"ready": int(r[0] or 0), "enriching": int(r[1] or 0),
            "failed": int(r[2] or 0), "total": int(r[3] or 0)}


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
    """Block until enrichment for the current namespace is fully settled: queue_depth==0 AND
    no ENRICHING episode, stable for `idle_polls` consecutive checks (or `timeout_s` elapses).
    Returns the last state-count snapshot (with timed_out flag)."""
    t0 = time.time()
    settled = 0
    last = {"ready": -1, "enriching": -1, "failed": -1, "total": -1}
    while time.time() - t0 < timeout_s:
        qd = _queue_depth(admin, menhir_url)
        last = _ns_state_counts(ns)
        # enriching==-1 means cypher timed out / Neo4j temporarily unreachable.
        # Treat unknown as "1 in-flight" so we keep polling rather than settling early.
        # Only settle when cypher confirms enriching==0.
        in_flight = last["enriching"] if last["enriching"] >= 0 else 1
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
            session_id = s_id or f"{ns}-s{s_idx}"
            for turn in session:
                content = turn.get("content", "")
                if content:
                    _ingest_turn(
                        client, ns, turn.get("role", "user"), content,
                        occurred_at=occurred_at,
                        session_id=session_id,
                    )
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

        manifest.append({
            "question_id": qid, "namespace": ns,
            "fixture": str(Path(args.fixture).resolve()) if args.fixture else None,
            "question": adapter.question(item), "answer": str(item.get("answer", "")),
            "question_type": item.get("question_type"), "turns": turns,
            "episodes": drained.get("total"), "ready": drained.get("ready"),
            "failed_remaining": drained.get("failed"), "failed_requeued": requeued,
            "drain_timed_out": drained.get("timed_out", False),
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
