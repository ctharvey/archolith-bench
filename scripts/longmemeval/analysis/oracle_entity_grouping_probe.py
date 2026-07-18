"""Oracle entity-grouping probe (terminal sidecar experiment, 2026-07-18).

Question (binary): when typed assertions are grouped by *resolved entities* (hand-labeled
oracle, bypassing lexical/coarse grouping), do supersession selection and delta derivation
recover the gold value?

  - If YES for a case, the blocker was entity/scope resolution -> graduate to the Menhir
    View design (real entity nodes).
  - If NO even with a perfect oracle grouping, the residual problem is attribute/state-family
    resolution or reasoning (mention-order-vs-truth, "previous"-value questions, extraction),
    NOT entity resolution.

Offline, deterministic, read-only. Reuses the real extractor (SupersededValueGraph) and its
real selection logic (_current_edge_ids) + delta fold; only the cluster key is overridden with
a hand-labeled oracle (entity, attribute). No graph, no network, no cost.

Run: .venv/Scripts/python.exe scripts/longmemeval/analysis/oracle_entity_grouping_probe.py
"""

from __future__ import annotations

from dataclasses import replace

from archolith_bench.harness.longmemeval import LongMemEvalMemoryAdapter
from archolith_bench.harness.value_nodes import ValueKind
from archolith_bench.harness.value_nodes_v2 import SupersededValueGraph

FIXTURE = "fixtures/longmemeval/knowledge_update_subset.json"

# Per-item oracle labels: (substring that identifies the source fact, value-match, oracle key).
# Each rule maps an extracted assertion to a resolved (entity, attribute) cluster. A value of
# None matches any value for that fact substring. Assertions matching no rule keep a unique
# singleton key (they cannot participate in supersession).
OracleRule = tuple[str, object, tuple[str, str]]

ORACLE: dict[str, dict[str, object]] = {
    "b6019101": {  # gold 5 MCU films watched (scope: MCU vs all films)
        "gold_kind": ValueKind.COUNT,
        "gold": "5",
        "rules": [
            ("4 MCU films", 4, ("mcu_films", "watched")),
            ("including 5 MCU", 5, ("mcu_films", "watched")),
            ("watched 12 films", 12, ("all_films", "watched")),
        ],
    },
    "f9e8c073": {  # gold five sessions attended (recency in a clean cluster)
        "gold_kind": ValueKind.COUNT,
        "gold": "5",
        "rules": [
            ("attend three sessions", 3, ("bereavement_sessions", "attended")),
            ("attending five sessions", 5, ("bereavement_sessions", "attended")),
        ],
    },
    "dad224aa": {  # gold 07:30 wake time Saturday (recency; 7:30 supersedes 8:30)
        "gold_kind": ValueKind.CLOCK_TIME,
        "gold": "07:30",
        "rules": [
            ("waking up around 8:30", "08:30", ("wake_saturday", "clock")),
            ("already waking up at 8:30", "08:30", ("wake_saturday", "clock")),
            ("like to wake up", "07:30", ("wake_saturday", "clock")),
        ],
    },
    "59524333": {  # gold 18:00 usual gym time (entity sep from meeting + recency)
        "gold_kind": ValueKind.CLOCK_TIME,
        "gold": "18:00",
        "rules": [
            ("gym sessions, which I usually go", "19:00", ("gym_time", "usual")),
            ("head to the gym, which is usually", "18:00", ("gym_time", "usual")),
            ("Tuesday afternoon at 2:00 pm", "14:00", ("meeting_time", "when")),
        ],
    },
    "71315a70": {  # gold [10,12] sculpture hours (single entity; recency decides)
        "gold_kind": ValueKind.DURATION,
        "gold": "10",  # normalized [10,12]; check membership below
        "rules": [
            ("spent around 5-6 hours", None, ("sculpture", "hours_spent")),
            ("already spent 10-12 hours", None, ("sculpture", "hours_spent")),
            ("spending a lot of time on my abstract ocean sculpture", None, ("sculpture", "hours_spent")),
        ],
    },
    "dfde3500": {  # gold Wednesday = Juan's day (entity: Juan vs Maria)
        "gold_kind": ValueKind.WEEKDAY,
        "gold": "wednesday",
        "rules": [
            ("class with Juan is on Wednesday", "wednesday", ("juan_meeting", "weekday")),
            ("We meet every Wednesday", "wednesday", ("juan_meeting", "weekday")),
            ("meeting Maria on Thursday", "thursday", ("maria_meeting", "weekday")),
        ],
    },
    "e66b632c": {  # gold 27:45 = PREVIOUS PB (earlier value; current-selection is wrong by design)
        "gold_kind": ValueKind.DURATION,
        "gold": "27",
        "rules": [
            ("personal best time of 27 minutes", 27, ("5k_pb_minutes", "finish")),
            ("personal best time of 26 minutes", 26, ("5k_pb_minutes", "finish")),
        ],
    },
    "69fee5aa": {  # gold 38 = 37 + delta (entity clean + delta fold)
        "gold_kind": ValueKind.COUNT,
        "gold": "38",
        "is_delta": True,
        "rules": [
            ("total of 37 coins", 37, ("pre1920_coins", "owned")),
        ],
    },
}


def _assign_oracle(graph: SupersededValueGraph, rules: list[OracleRule]) -> None:
    """Overwrite each edge's cluster_key with its oracle (entity, attribute), leaving the real
    correction markers + ordinal intact. Unmatched edges get a unique singleton key."""
    for i, edge in enumerate(graph.edges):
        meta = graph._meta.get(edge.edge_id)
        if meta is None:
            continue
        value = graph.values[edge.target_node_id]
        oracle_key: tuple = ("__unmatched__", str(i))
        for sub, val, key in rules:
            if sub in edge.fact and (val is None or str(value.normalized) == str(val) or (
                isinstance(value.normalized, list) and val in value.normalized
            )):
                oracle_key = key
                break
        graph._meta[edge.edge_id] = replace(meta, cluster_key=oracle_key)


def _current_values_for_key(graph: SupersededValueGraph, oracle_key: tuple) -> list[str]:
    current_ids, _ = graph._current_edge_ids()
    out = []
    for edge in graph.edges:
        meta = graph._meta.get(edge.edge_id)
        if meta and meta.cluster_key == oracle_key and edge.edge_id in current_ids:
            out.append(str(graph.values[edge.target_node_id].normalized))
    return out


def main() -> None:
    adapter = LongMemEvalMemoryAdapter()
    items = adapter.load_items("knowledge-update", 78, FIXTURE)
    by_id = {(it.get("question_id") or it.get("qid") or it.get("task_id")): it for it in items}

    print(f"{'item':10} {'gold':>10}  outcome  detail")
    print("-" * 92)
    fixed, not_entity = [], []
    for qid, spec in ORACLE.items():
        it = by_id[qid]
        graph = SupersededValueGraph.from_item(f"oracle-{qid}", it, adapter.sessions(it), grouping="coarse")
        _assign_oracle(graph, spec["rules"])  # type: ignore[arg-type]

        gold = spec["gold"]
        if spec.get("is_delta"):
            # Delta fold reads the counted noun from the coarse cluster key; run it on the
            # entity-clean coarse graph (v5's real path, which already excludes the "pre-1920"
            # year noise = an entity-resolution effect) rather than the oracle-reassigned keys.
            clean = SupersededValueGraph.from_item(
                f"delta-{qid}", it, adapter.sessions(it), grouping="coarse"
            )
            hints = clean._derived_hints(adapter.question(it))
            hit = any(f"~{gold}" in h for h in hints)
            detail = (hints[0][:70] if hints else "no derived hint")
        else:
            # target entity cluster = the one holding a gold-valued assertion
            target_key = None
            for _sub, _val, key in spec["rules"]:  # type: ignore[misc]
                if str(_val) == str(gold) or (spec["gold_kind"] is ValueKind.DURATION and key[0] in ("sculpture", "5k_pb_minutes")):
                    target_key = key
            currents = _current_values_for_key(graph, target_key) if target_key else []
            joined = " ".join(currents)
            hit = gold in joined or (spec["gold_kind"] is ValueKind.DURATION and f"[{gold}," in joined)
            detail = f"entity={target_key} current={currents}"

        if hit:
            fixed.append(qid)
            outcome = "FIXED  "
        else:
            not_entity.append(qid)
            outcome = "NOT-ENT"
        print(f"{qid:10} {str(gold):>10}  {outcome}  {detail[:66]}")

    print("-" * 92)
    print(f"FIXED by oracle entity grouping ({len(fixed)}/8): {fixed}")
    print(f"NOT fixed - reasoning/extraction ({len(not_entity)}/8): {not_entity}")


if __name__ == "__main__":
    main()
