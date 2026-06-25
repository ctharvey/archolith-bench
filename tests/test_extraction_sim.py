"""Offline tests for the backend extraction simulation (stub OpenAI client, no network)."""

from __future__ import annotations

import json

import httpx

from archolith_bench.extraction_sim import CORPUS, ModelResult, render_results, simulate_model


class _StubHttpResp:
    def __init__(self, status_code, content_json=None, text=""):
        self.status_code = status_code
        self._json = content_json
        self.text = text

    def json(self):
        return {"choices": [{"message": {"content": json.dumps(self._json)}}]}


def _install_stub_httpx(monkeypatch, *, fail_json_schema=False):
    """Patch httpx.Client.post to return gold-ish JSON per pipeline stage (no network)."""
    def fake_post(self, url, *, json=None, headers=None, **kw):  # noqa: A002, ARG001
        body = json or {}
        rf = body.get("response_format", {})
        if fail_json_schema and rf.get("type") == "json_schema":
            return _StubHttpResp(400, text="This response_format type is unavailable now")
        sys_txt = " ".join(m["content"] for m in body.get("messages", []) if m["role"] == "system").lower()
        if "resolutions" in sys_txt:
            return _StubHttpResp(200, {"resolutions": []})
        if "edges" in sys_txt or "relationships" in sys_txt:
            return _StubHttpResp(200, {"edges": [{"source": "maria", "target": "lisbon",
                                                  "fact": "maria moved to lisbon"}]})
        return _StubHttpResp(200, {"entities": [{"name": "maria"}, {"name": "lisbon"},
                                               {"name": "berlin"}, {"name": "nuvei"}]})

    monkeypatch.setattr(httpx.Client, "post", fake_post)


def test_simulate_model_runs_pipeline_and_scores(monkeypatch):
    _install_stub_httpx(monkeypatch)
    r = simulate_model("stub", "http://x/v1", "k", "stub-model", corpus=CORPUS[:2])
    assert r.error == ""
    assert r.mode == "json_schema"
    assert r.episodes == 2
    assert r.total_calls == 6  # 3 calls/episode * 2
    assert r.valid_json_rate == 1.0
    assert r.mean_entity_recall > 0  # echoed gold entities for episode 1


def test_simulate_falls_back_to_json_object_when_schema_unavailable(monkeypatch):
    _install_stub_httpx(monkeypatch, fail_json_schema=True)
    r = simulate_model("ds", "https://api.deepseek.com/v1", "k", "deepseek-v4-flash", corpus=CORPUS[:1])
    assert r.error == ""
    assert r.mode == "json_object+prompt"  # detected the json_schema rejection and fell back
    assert r.episodes == 1


def test_render_results_table_and_ranking(monkeypatch):
    _install_stub_httpx(monkeypatch)
    fast = simulate_model("fast", "http://x/v1", "k", "m", corpus=CORPUS[:1])
    out = render_results([fast])
    assert "model" in out and "call_p50" in out and "fact_rec" in out
    assert "fast" in out


def test_modelresult_percentiles():
    r = ModelResult(label="x", model="m", mode="json_schema")
    r.call_latencies = [0.1, 0.2, 0.3, 0.4, 1.0]
    assert r.call_max == 1.0
    assert r.call_p50 == 0.3
