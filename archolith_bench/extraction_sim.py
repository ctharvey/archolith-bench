"""Backend-extraction simulation for picking a menhir extraction model.

A single chat call is not representative: menhir/graphiti enriches each episode with a
MULTI-CALL pipeline (extract entities -> resolve/dedupe against the growing graph ->
extract edges/facts), run over many episodes. The tail latency and real throughput
only show up under that sustained, multi-stage load. This replays a faithful 3-stage
pipeline over a small conversation corpus against any OpenAI-compatible model and
reports latency distribution, throughput, and extraction quality, so models are
compared on what they will actually do on the backend -- not a toy single call.

Mirrors the menhir path: tries json_schema, falls back to json_object + schema-in-prompt
(deepseek), and disables thinking for deepseek targets.
"""

from __future__ import annotations

import json
import statistics
import time
from dataclasses import dataclass, field

# --- Corpus: conversation episodes with gold entities + gold facts (substring-scored). ---
CORPUS: list[dict] = [
    {
        "text": "user: Hi, I'm Maria. I moved to Lisbon from Berlin for a job at a fintech called Nuvei.",
        "entities": ["maria", "lisbon", "berlin", "nuvei"],
        "facts": ["maria moved to lisbon", "maria works at nuvei"],
    },
    {
        "text": "user: I bought a 2022 Tesla Model 3, midnight silver. My manager Tomas is great.",
        "entities": ["tesla model 3", "tomas"],
        "facts": ["maria owns a tesla model 3", "tomas is maria's manager"],
    },
    {
        "text": "user: On weekends I surf at Carcavelos beach with my dog Pixel.",
        "entities": ["carcavelos", "pixel"],
        "facts": ["maria surfs at carcavelos", "pixel is maria's dog"],
    },
    {
        "text": "user: Tomas introduced me to Sofia, our designer. We're shipping a feature called QuickPay in March.",
        "entities": ["sofia", "quickpay"],
        "facts": ["sofia is a designer", "quickpay ships in march"],
    },
    {
        "text": "user: My Tesla's range dropped, so I booked service at the Cascais center next Tuesday.",
        "entities": ["cascais"],
        "facts": ["tesla service booked at cascais"],
    },
]

_ENT_SCHEMA = {"type": "object", "properties": {"entities": {"type": "array", "items": {
    "type": "object", "properties": {"name": {"type": "string"}, "type": {"type": "string"}},
    "required": ["name"]}}}, "required": ["entities"]}
_RES_SCHEMA = {"type": "object", "properties": {"resolutions": {"type": "array", "items": {
    "type": "object", "properties": {"name": {"type": "string"}, "duplicate_of": {"type": "string"}},
    "required": ["name"]}}}, "required": ["resolutions"]}
_EDGE_SCHEMA = {"type": "object", "properties": {"edges": {"type": "array", "items": {
    "type": "object", "properties": {"source": {"type": "string"}, "target": {"type": "string"},
    "fact": {"type": "string"}}, "required": ["fact"]}}}, "required": ["edges"]}


# (cache_hit_in, cache_miss_in, output) USD per 1M tokens. Matched by substring on model.
# Cached-input rates are what make a repetitive-prefix workload (system prompt + schema)
# cheap; where a provider has no separate cache rate, cache_hit == cache_miss.
PRICING: dict[str, tuple[float, float, float]] = {
    # OpenAI (June 2026 published rates: cache-hit / input / output per 1M)
    "gpt-5.2-pro": (21.00, 21.00, 168.00),
    "gpt-5.2": (0.175, 1.75, 14.00),
    "gpt-5.1": (0.125, 1.25, 10.00),
    "gpt-5-nano": (0.005, 0.05, 0.40),
    "gpt-5-mini": (0.025, 0.25, 2.00),
    "gpt-5-pro": (15.00, 15.00, 120.00),
    "gpt-5": (0.125, 1.25, 10.00),
    "gpt-4.1-nano": (0.025, 0.10, 0.40),
    "gpt-4.1-mini": (0.10, 0.40, 1.60),
    "gpt-4.1": (0.50, 2.00, 8.00),
    "gpt-4o-mini": (0.075, 0.15, 0.60),
    "gpt-4o": (1.25, 2.50, 10.00),
    # DeepSeek (api-docs.deepseek.com/quick_start/pricing)
    "deepseek-v4-flash": (0.0028, 0.14, 0.28),
    "deepseek-v4-pro": (0.003625, 0.435, 0.87),
    # Google (cloud.google.com/.../generative-ai/pricing) -- Global standard tier
    "gemini-3.1-flash-lite": (0.025, 0.25, 1.50),   # 3.x is pricier than 2.5: output $1.50 (3.75x nano)
    "gemini-3.5-flash": (0.15, 1.50, 9.00),
    "gemini-2.5-flash-lite": (0.01, 0.10, 0.40),
    "gemini-2.5-flash": (0.03, 0.30, 2.50),
    # Groq (groq.com/pricing) -- cache hit is 50% off input
    "llama-3.1-8b": (0.025, 0.05, 0.08),
    "llama-3.3-70b": (0.295, 0.59, 0.79),
    "gpt-oss-20b": (0.0375, 0.075, 0.30),
    "gpt-oss-120b": (0.075, 0.15, 0.60),
    # Cerebras (cerebras.ai/pricing) -- no separate cache rate, so hit == input.
    # Provider-scoped ("cerebras/") because Cerebras charges more than Groq for the same
    # open weights (e.g. gpt-oss-120b: $0.35/$0.75 vs Groq $0.15/$0.60). Free tier = $0,
    # but the list-price estimate is what the $/1k column reports.
    "cerebras/gpt-oss-120b": (0.35, 0.35, 0.75),
    "cerebras/qwen-3-32b": (0.40, 0.40, 0.80),
    "cerebras/llama-3.3-70b": (0.85, 0.85, 1.20),
    "cerebras/llama3.1-8b": (0.10, 0.10, 0.10),
}


def _pricing_for(model: str, base_url: str = "") -> tuple[float, float, float] | None:
    """Match the most specific (longest) pricing key contained in the model name, so
    'gpt-5-nano' resolves to gpt-5-nano rather than the shorter 'gpt-5'.

    Provider-scoped keys (containing '/') are matched first when the base_url identifies
    that provider, so a Cerebras-hosted open model is priced at Cerebras rates rather than
    colliding with the cheaper Groq entry for the same weights."""
    low = model.lower()
    keys = sorted(PRICING, key=len, reverse=True)
    if "cerebras" in base_url.lower():
        for key in keys:
            if key.startswith("cerebras/") and key.split("/", 1)[1] in low:
                return PRICING[key]
    for key in keys:
        if "/" in key:  # provider-scoped; only used in the provider pass above
            continue
        if key in low:
            return PRICING[key]
    return None


@dataclass
class ModelResult:
    label: str
    model: str
    mode: str  # json_schema | json_object+prompt
    base_url: str = ""
    episodes: int = 0
    call_latencies: list[float] = field(default_factory=list)
    episode_latencies: list[float] = field(default_factory=list)
    valid_json: int = 0
    total_calls: int = 0
    entity_recall: list[float] = field(default_factory=list)
    fact_recall: list[float] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    wall_clock_s: float = 0.0
    error: str = ""
    last_call_error: str = ""

    @property
    def cache_hit_rate(self) -> float:
        return (self.cached_input_tokens / self.input_tokens) if self.input_tokens else 0.0

    def cost_per_1k_episodes(self) -> float | None:
        """Estimated USD per 1,000 episodes, using the measured cache hit/miss split."""
        p = _pricing_for(self.model, self.base_url)
        if p is None or self.episodes == 0:
            return None
        hit_in, miss_in, out = p
        miss = max(0, self.input_tokens - self.cached_input_tokens)
        cost = (self.cached_input_tokens * hit_in + miss * miss_in + self.output_tokens * out) / 1_000_000
        return cost / self.episodes * 1000

    def _p(self, q: float) -> float:
        if not self.call_latencies:
            return 0.0
        xs = sorted(self.call_latencies)
        i = min(len(xs) - 1, int(q * len(xs)))
        return xs[i]

    @property
    def call_p50(self) -> float: return self._p(0.50)
    @property
    def call_p95(self) -> float: return self._p(0.95)
    @property
    def call_max(self) -> float: return max(self.call_latencies) if self.call_latencies else 0.0
    @property
    def episode_avg(self) -> float: return statistics.mean(self.episode_latencies) if self.episode_latencies else 0.0
    @property
    def valid_json_rate(self) -> float: return (self.valid_json / self.total_calls) if self.total_calls else 0.0
    @property
    def mean_entity_recall(self) -> float: return statistics.mean(self.entity_recall) if self.entity_recall else 0.0
    @property
    def mean_fact_recall(self) -> float: return statistics.mean(self.fact_recall) if self.fact_recall else 0.0


def _recall(gold: list[str], found_blob: str) -> float:
    """Fraction of gold strings present as a substring (used for single-token entities)."""
    if not gold:
        return 1.0
    low = found_blob.lower()
    return sum(1 for g in gold if g.lower() in low) / len(gold)


_STOP = {"a", "an", "the", "is", "was", "are", "to", "of", "in", "at", "on", "for", "with",
         "and", "my", "our", "her", "his", "their", "by", "from", "as"}


def _fact_recall(gold_facts: list[str], found_blob: str) -> float:
    """Token-overlap recall: a gold fact counts when most of its content words appear in
    the extracted edges (LLMs phrase relationships differently, so exact-string is wrong)."""
    if not gold_facts:
        return 1.0
    low = found_blob.lower()
    matched = 0
    for fact in gold_facts:
        toks = [w for w in fact.lower().replace("'", " ").split() if len(w) > 2 and w not in _STOP]
        if not toks:
            continue
        present = sum(1 for w in toks if w in low)
        if present / len(toks) >= 0.6:
            matched += 1
    return matched / len(gold_facts)


class _SchemaUnavailable(Exception):
    """Raised when the endpoint rejects the json_schema response_format."""


def simulate_model(label: str, base_url: str, api_key: str, model: str, *, corpus=None, repeats: int = 1):
    """Run the 3-stage extraction pipeline over the corpus and return a ModelResult.

    Uses httpx directly against the OpenAI-compatible /chat/completions endpoint (the
    same transport the rest of the bench uses), so any OpenAI-compatible provider works.
    """
    import httpx

    corpus = corpus or CORPUS
    res = ModelResult(label=label, model=model, mode="json_schema", base_url=base_url)
    is_deepseek = "deepseek" in model.lower() or "deepseek" in base_url.lower()
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    http = httpx.Client(timeout=60.0)

    low = model.lower()
    needs_completion_tokens = low.startswith(("gpt-5", "o1", "o3", "o4"))

    def _call(system: str, user: str, schema: dict) -> tuple[float, str, bool]:
        msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        body: dict = {"model": model, "messages": msgs}
        if needs_completion_tokens:
            # gpt-5 / o-series require max_completion_tokens and only the default temperature.
            # reasoning_effort=minimal disables thinking (448 reasoning tokens -> 0, ~4x faster);
            # extraction is structured and needs no chain-of-thought.
            body["max_completion_tokens"] = 800
            body["reasoning_effort"] = "minimal"
        else:
            body["max_tokens"] = 500
            body["temperature"] = 0.0
        if res.mode == "json_schema":
            body["response_format"] = {"type": "json_schema", "json_schema": {"name": "out", "schema": schema}}
        else:
            body["response_format"] = {"type": "json_object"}
            msgs.append({"role": "system", "content": "Respond ONLY with JSON matching this schema: " + json.dumps(schema)})
        if is_deepseek:
            body["thinking"] = {"type": "disabled"}  # speed; deepseek-only
        t = time.time()
        resp = http.post(url, json=body, headers=headers)
        dt = time.time() - t
        if resp.status_code != 200:
            txt = resp.text.lower()
            if resp.status_code == 400 and ("response_format" in txt or "unavailable" in txt or "json_schema" in txt):
                raise _SchemaUnavailable(resp.text[:160])
            raise RuntimeError(f"{resp.status_code}: {resp.text[:140]}")
        data = resp.json()
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "") or ""
        usage = data.get("usage", {}) or {}
        ok = True
        try:
            json.loads(text)
        except Exception:
            ok = False
        return dt, text, ok, usage

    # Detect response_format mode once (json_schema, else json_object+prompt like menhir).
    try:
        _call("Extract entities as JSON {\"entities\":[]}.", "user: test ping.", _ENT_SCHEMA)
    except _SchemaUnavailable:
        res.mode = "json_object+prompt"
    except Exception as e:
        res.error = str(e)[:160]
        return res

    def _safe_call(system: str, user: str, schema: dict) -> tuple[float, str, bool, dict]:
        """Per-call resilience: a single failed call (rate limit, transient, or a model
        that can't conform to the schema) is recorded as invalid JSON and the run
        continues, instead of aborting the whole model."""
        try:
            return _call(system, user, schema)
        except Exception as e:
            res.last_call_error = str(e)[:120]
            return 0.0, "", False, {}

    def _record(dt: float, ok: bool, usage: dict) -> None:
        if dt > 0:
            res.call_latencies.append(dt)
        res.total_calls += 1
        if ok:
            res.valid_json += 1
        res.input_tokens += int(usage.get("prompt_tokens") or 0)
        res.output_tokens += int(usage.get("completion_tokens") or 0)
        # DeepSeek reports prompt_cache_hit_tokens; OpenAI nests cached_tokens.
        cached = usage.get("prompt_cache_hit_tokens")
        if cached is None:
            cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens")
        res.cached_input_tokens += int(cached or 0)

    known_entities: list[str] = []
    wall_start = time.time()
    try:
        for _ in range(repeats):
            for ep in corpus:
                ep_start = time.time()
                # Stage 1: entity extraction
                dt, text, ok, usage = _safe_call(
                    "Extract every distinct named entity (people, places, orgs, products) from the message. "
                    "Return JSON {\"entities\":[{\"name\":..,\"type\":..}]}.",
                    ep["text"], _ENT_SCHEMA)
                _record(dt, ok, usage)
                res.entity_recall.append(_recall(ep["entities"], text))
                try:
                    names = [str(e.get("name", "")) for e in json.loads(text).get("entities", []) if isinstance(e, dict)]
                except Exception:
                    names = []

                # Stage 2: entity resolution / dedupe against the growing graph
                dt, text, ok, usage = _safe_call(
                    "Given NEW entities and EXISTING entities, return JSON {\"resolutions\":[{\"name\":..,"
                    "\"duplicate_of\":..}]} marking any new entity that duplicates an existing one.",
                    f"NEW: {json.dumps(names)}\nEXISTING: {json.dumps(known_entities[-40:])}", _RES_SCHEMA)
                _record(dt, ok, usage)
                known_entities.extend(n for n in names if n)

                # Stage 3: edge / fact extraction
                dt, text, ok, usage = _safe_call(
                    "Extract relationships/facts between the entities in the message. "
                    "Return JSON {\"edges\":[{\"source\":..,\"target\":..,\"fact\":..}]}.",
                    f"MESSAGE: {ep['text']}\nENTITIES: {json.dumps(names)}", _EDGE_SCHEMA)
                _record(dt, ok, usage)
                res.fact_recall.append(_fact_recall(ep["facts"], text))

                res.episode_latencies.append(time.time() - ep_start)
                res.episodes += 1
    except Exception as e:
        res.error = str(e)[:160]
    finally:
        http.close()
    res.wall_clock_s = time.time() - wall_start
    return res


def _read_env_file(path: str, key: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith(key + "="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        return ""
    return ""


def default_targets() -> list[dict]:
    """Build the target list from available keys (workspace .env files + env vars).

    Fast-provider entries (Groq/Gemini/Cerebras) are included only if their key env var
    is set, so adding a key auto-enables that target -- no code change.
    """
    import os

    menhir_env = r"C:\Users\thron\IdeaProjects\projects\archolith\menhir\.env"
    delegate_env = r"C:\Users\thron\IdeaProjects\projects\ctharvey\cth.mcp.delegate\.env"

    def _key(*envvars: str, files_keys: tuple[tuple[str, str], ...] = ()) -> str:
        """First non-empty value from env vars, then (file, key) pairs."""
        for v in envvars:
            if os.getenv(v):
                return os.getenv(v)
        for path, k in files_keys:
            val = _read_env_file(path, k)
            if val:
                return val
        return ""

    openai_key = _key("OPENAI_API_KEY", files_keys=((menhir_env, "OPENAI_API_KEY"),))
    deepseek_key = _key("DEEPSEEK_API_KEY", files_keys=((delegate_env, "DELEGATE_API_KEY"),))
    groq_key = _key("GROQ_API_KEY", files_keys=((menhir_env, "GROQ_API_KEY"),))
    gemini_key = _key("GEMINI_API_KEY", "GOOGLE_API_KEY",
                      files_keys=((menhir_env, "GEMINI_API_KEY"), (menhir_env, "GOOGLE_API_KEY")))
    cerebras_key = _key("CEREBRAS_API_KEY", files_keys=((menhir_env, "CEREBRAS_API_KEY"),))

    candidates = [
        ("gpt-5-nano", "https://api.openai.com/v1", openai_key, "gpt-5-nano"),
        ("gpt-5-mini", "https://api.openai.com/v1", openai_key, "gpt-5-mini"),
        ("gpt-4.1-nano", "https://api.openai.com/v1", openai_key, "gpt-4.1-nano"),
        ("gpt-4.1-mini", "https://api.openai.com/v1", openai_key, "gpt-4.1-mini"),
        ("gpt-4o-mini", "https://api.openai.com/v1", openai_key, "gpt-4o-mini"),
        ("deepseek-v4-flash", "https://api.deepseek.com/v1", deepseek_key, "deepseek-v4-flash"),
        # Fast-inference providers: enabled when the key is present (env var or .env).
        ("groq-llama3.1-8b", "https://api.groq.com/openai/v1", groq_key, "llama-3.1-8b-instant"),
        ("groq-llama3.3-70b", "https://api.groq.com/openai/v1", groq_key, "llama-3.3-70b-versatile"),
        ("groq-gpt-oss-20b", "https://api.groq.com/openai/v1", groq_key, "openai/gpt-oss-20b"),
        ("gemini-3.1-flash-lite", "https://generativelanguage.googleapis.com/v1beta/openai/",
         gemini_key, "gemini-3.1-flash-lite"),
        ("gemini-2.5-flash-lite", "https://generativelanguage.googleapis.com/v1beta/openai/",
         gemini_key, "gemini-2.5-flash-lite"),
        # Cerebras wafer-scale (OpenAI-compatible): free tier 30 RPM / 1M TPD.
        # gpt-oss-120b runs ~3000 tk/s; qwen-3-32b has a strong non-thinking mode.
        ("cerebras-gpt-oss-120b", "https://api.cerebras.ai/v1", cerebras_key, "gpt-oss-120b"),
        ("cerebras-qwen3-32b", "https://api.cerebras.ai/v1", cerebras_key, "qwen-3-32b"),
        ("cerebras-llama3.3-70b", "https://api.cerebras.ai/v1", cerebras_key, "llama-3.3-70b"),
    ]
    return [{"label": lbl, "base_url": url, "api_key": key, "model": m}
            for (lbl, url, key, m) in candidates if key]


def render_results(results: list[ModelResult]) -> str:
    lines = [
        "Backend extraction simulation (3 calls/episode: entities -> resolve -> edges)",
        f"{'model':22}{'mode':18}{'ep/s':>7}{'call_p50':>10}{'call_p95':>10}"
        f"{'ep_avg':>9}{'json':>7}{'ent_rec':>9}{'fact_rec':>9}{'cacheHit':>9}{'$/1k_ep':>10}",
        "-" * 130,
    ]
    # rank by episode throughput (episodes / wall clock)
    for r in sorted(results, key=lambda x: (x.error != "", -(x.episodes / x.wall_clock_s if x.wall_clock_s else 0))):
        if r.error:
            lines.append(f"{r.label:22}ERROR  {r.error}")
            continue
        eps = r.episodes / r.wall_clock_s if r.wall_clock_s else 0.0
        cost = r.cost_per_1k_episodes()
        cost_s = f"${cost:8.2f}" if cost is not None else "   n/a"
        lines.append(
            f"{r.label:22}{r.mode:18}{eps:>7.2f}{r.call_p50:>9.2f}s{r.call_p95:>9.2f}s"
            f"{r.episode_avg:>8.2f}s{r.valid_json_rate:>7.0%}{r.mean_entity_recall:>9.2f}{r.mean_fact_recall:>9.2f}"
            f"{r.cache_hit_rate:>9.0%}{cost_s:>10}"
        )
    lines.append("")
    lines.append("$/1k_ep = est. extraction cost per 1,000 episodes using the MEASURED cache hit/miss split.")
    lines.append("Note: cold-run cache-hit rates understate production; a warm cache (repeated prefixes) lowers $ further.")
    return "\n".join(lines)
