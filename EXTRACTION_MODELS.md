# Choosing an Extraction Model

Graph-memory systems (menhir / Graphiti and similar) turn each conversation turn into
graph structure with a **multi-call LLM pipeline per episode**: extract entities →
resolve/dedupe them against the existing graph → extract edges/facts. At scale that is
hundreds of thousands of small, structured-JSON calls, so the choice of *extraction
model* is a real speed / cost / quality decision — not a place to default to whatever
you use for chat.

This page is the data behind that decision. Everything here is measured with
[`archolith-bench extraction-bench`](#reproduce-it), which replays the actual 3-call
pipeline over a conversation corpus against any OpenAI-compatible model.

## TL;DR

- **Quality is basically a tie** among capable small models — entity/relation extraction
  is an easy, structured task. So the decision is **speed and cost**, not accuracy.
- **Best all-round: `gpt-4.1-nano`** — ~0.5 s/call, ~$0.09 per 1k episodes, native
  structured output, no rate-limit walls.
- **Cheapest: `deepseek-v4-flash`** — ~$0.05 per 1k episodes thanks to aggressive prompt
  caching (the repeated system-prompt + schema prefix is ~free), but the slowest of the
  mainstream options.
- **Fastest: Groq `llama-3.3-70b`** on LPU hardware (~3× nano), but pricier per token and
  the free tier can't sustain a production run.
- **Avoid for extraction:** reasoning models (gpt-5-nano/mini, default Gemini-Flash
  thinking) — they "think" before answering, which is wasted latency for structured
  extraction. Disable thinking if you must use them (see below).

## What we measure

Per model the simulation runs the real backend pipeline — **3 calls per episode** over a
multi-episode corpus (so the entity-resolution context grows like production) — and
reports:

- **`call_p50` / `call_p95`** — per-call latency distribution (the tail matters: some
  providers spike to 10–20 s under load).
- **`ep_avg`, `ep/s`** — per-episode latency and throughput.
- **`ent_rec` / `fact_rec`** — entity and fact recall vs a gold set.
- **`json`** — valid-JSON rate (does it return parseable structured output at all).
- **`cacheHit` / `$/1k_ep`** — measured prompt-cache hit rate and estimated cost per 1,000
  episodes using the real cache hit/miss split and published pricing.

## Results

Measured June 2026, `--repeats 2` (cold cache unless noted). Latency is provider- and
load-dependent; re-run for your own region/tier.

| model | provider | call p50 | ep_avg | ent_rec | fact_rec | cache hit | $/1k ep |
|-------|----------|---------:|-------:|--------:|---------:|----------:|--------:|
| **llama-3.3-70b** | Groq (LPU) | **0.35 s** | **1.10 s** | 1.00 | 0.80 | – | $0.53 |
| **gpt-4.1-nano** | OpenAI | 0.54 s | 1.72 s | 0.90 | 0.80 | 0% | **$0.09** |
| gpt-4.1-mini | OpenAI | 0.81 s | 2.55 s | 1.00 | 0.85 | 0% | $0.32 |
| gpt-4o-mini | OpenAI | 0.89 s | 2.85 s | 1.00 | 0.80 | 0% | $0.12 |
| **deepseek-v4-flash** | DeepSeek | 1.19 s | 3.52 s | 1.00 | 0.80 | **74%** | **$0.05** |
| gpt-5-nano (thinking off) | OpenAI | 1.20 s | 4.07 s | 0.80 | 0.90 | 0% | $0.11 |
| gpt-5-mini (thinking off) | OpenAI | 1.39 s | 4.81 s | 1.00 | 0.85 | 0% | $0.46 |
| gemini-2.5-flash | Google | 1.52 s | 4.74 s | 1.00 | **0.40** | 0% | $0.27 |

> `cacheHit` is measured cold here; in production the repeated system-prompt + schema
> prefix warms the cache and pushes cost lower — most for providers with a deep cache
> discount (DeepSeek, Gemini, Groq).

## Pricing (USD per 1M tokens)

The cached-input rate is what makes a repetitive-prefix workload cheap — every extraction
call repeats the same system prompt and JSON schema.

| model | cache-hit in | input | output |
|-------|-------------:|------:|-------:|
| gpt-5-nano | $0.005 | $0.05 | $0.40 |
| gpt-5-mini | $0.025 | $0.25 | $2.00 |
| gpt-4.1-nano | $0.025 | $0.10 | $0.40 |
| gpt-4.1-mini | $0.10 | $0.40 | $1.60 |
| gpt-4o-mini | $0.075 | $0.15 | $0.60 |
| deepseek-v4-flash | **$0.0028** | $0.14 | $0.28 |
| gemini-2.5-flash-lite | $0.01 | $0.10 | $0.40 |
| gemini-2.5-flash | $0.03 | $0.30 | $2.50 |
| groq llama-3.1-8b | $0.025 | $0.05 | $0.08 |
| groq llama-3.3-70b | $0.295 | $0.59 | $0.79 |
| groq gpt-oss-20b | $0.0375 | $0.075 | $0.30 |

Sources: OpenAI, [DeepSeek](https://api-docs.deepseek.com/quick_start/pricing/),
[Google](https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing),
[Groq](https://groq.com/pricing). Always confirm against the provider — prices move.

## Key findings

### 1. Quality is a tie — optimize for speed and cost
Every capable small model hit ~0.9–1.0 entity recall and ~0.8 fact recall with 100% valid
JSON. Extraction is a structured, low-creativity task; you do not need a frontier model.

### 2. Caching flips the cost ranking
DeepSeek looks mid-priced on paper ($0.14/1M input) but is the **cheapest in practice**:
its cache-hit rate of ~$0.0028/1M is **50× cheaper**, and our workload caches ~70%+ of
input (stable system prompt + schema). If a provider has a deep cache tier, structure the
prompt so the **stable parts are the prefix** and the variable episode text comes last.

### 3. Reasoning models are the wrong tool — disable thinking
`gpt-5-nano` spends ~450 "reasoning" tokens before answering a trivial extraction, costing
~4.3 s/call. Turning thinking off recovers most of the speed:

| flag | effect |
|------|--------|
| OpenAI gpt-5 / o-series | `reasoning_effort: "minimal"` → reasoning tokens 448 → 0, 4.3 s → 1.1 s |
| Gemini 2.5 | `thinking_budget: 0` (Flash thinks by default; Flash-Lite does not) |
| DeepSeek v4 | `thinking: {"type": "disabled"}` (the only accepted form) |

Even with thinking off, gpt-5-nano (1.2 s/call) stayed ~2× slower than gpt-4.1-nano with
*lower* entity recall — so for this task plain `gpt-4.1-nano` wins.

### 4. Structured-output support varies — and breaks silently
- **DeepSeek** rejects the `json_schema` response format entirely (HTTP 400 "unavailable").
  Use `response_format: json_object` **and put the schema in the prompt**, or it returns
  generic JSON and extracts *zero* entities.
- **Groq `gpt-oss`** failed JSON validation under `json_object` on some prompts.
- **OpenAI / Gemini** support `json_schema` natively and were the most reliable.

A good harness probes this per-model (try `json_schema`, fall back to `json_object` +
schema-in-prompt) rather than trusting a spec sheet.

### 5. Speed leaders need a paid tier
Groq's LPU (`llama-3.3-70b` at 0.35 s/call) and Cerebras are the fastest by far, but Groq's
**free tier is 30 RPM / 6,000 TPM / 14,400 RPD** — the 6K tokens/minute cap is the real
ceiling for schema-heavy calls and 429s quickly. A production-scale run (hundreds of
thousands of calls) needs the paid Developer tier.

## Recommendation

| if you want… | pick | notes |
|--------------|------|-------|
| **Sensible default** | `gpt-4.1-nano` | fast, cheap, reliable json_schema, no rate-limit pain |
| **Lowest cost at scale** | `deepseek-v4-flash` | caching makes it cheapest; slower; needs json_object + schema-in-prompt |
| **Lowest latency** | Groq `llama-3.3-70b` (paid tier) | ~3× faster; pay-to-scale |
| **All-Google stack** | `gemini-2.5-flash-lite` | cheap; set `thinking_budget: 0`; avoid full Flash for extraction |
| **Avoid** | gpt-5-nano/mini, default Gemini-Flash thinking | reasoning overhead for no quality gain |

## Not yet tested (PRs welcome)

Wired or easy to add — drop the provider key and re-run:

- **Cerebras** (`llama-3.3-70b` / `llama-3.1-8b`) — the other wafer-scale speed leader.
- **Groq `gpt-oss-20b/120b`** — fix the json_object validation path first.
- **Gemini 2.5 Flash-Lite** — cheap + thinking-off by default (503'd transiently in our run).
- **Mistral** `ministral-3b/8b`, **Qwen** 2.5/3, **Llama-4 Scout** — small, fast, cheap.

## Reproduce it

```sh
# Keys are read from env or your menhir/.env; fast providers auto-enable when present.
export OPENAI_API_KEY=...        # GROQ_API_KEY / GEMINI_API_KEY / CEREBRAS_API_KEY optional
archolith-bench extraction-bench --repeats 2
archolith-bench extraction-bench --repeats 2 --exclude gpt-5   # skip slow reasoning models
```

The harness replays the real 3-call pipeline, mirrors the menhir path (json_schema with a
json_object + schema-in-prompt fallback, thinking disabled per provider), and reports the
speed / quality / cache-aware-cost table above. Numbers are latency- and tier-dependent —
**run it for your own keys and region before committing to a model.**
