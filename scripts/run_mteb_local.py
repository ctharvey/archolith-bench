"""Run a real MTEB task against a local OpenAI-compatible embeddings endpoint.

Baseline measurement of an embedding model (no proxy A/B). Defaults to the local
LM Studio server. Usage:
    python scripts/run_mteb_local.py [task] [limit_corpus]

This remains a standalone measurement script instead of reusing `MtebAdapter`
because it drives the official in-process MTEB encoder API directly and writes
MTEB's native output folder. `MtebAdapter` is the archolith-bench harness wrapper
that parses or shells out per arm for uniform evidence reporting.
"""

from __future__ import annotations

import os
import sys
import time

import httpx
import numpy as np

BASE = os.getenv("EMBEDDINGS_BASE_URL", "http://localhost:1234/v1").rstrip("/")
MODEL = os.getenv("EMBEDDINGS_MODEL", "text-embedding-nomic-embed-text-v1.5")
API_KEY = os.getenv("EMBEDDINGS_API_KEY") or os.getenv("OPENAI_API_KEY") or "lm-studio"
TASK = sys.argv[1] if len(sys.argv) > 1 else "SciFact"

_client = httpx.Client(timeout=120)


def _post_batch(batch: list[str], headers: dict, max_retries: int = 4) -> list[list[float]]:
    """POST one batch, backing off on transient 429s (respecting Retry-After)."""
    for attempt in range(max_retries + 1):
        r = _client.post(f"{BASE}/embeddings", json={"model": MODEL, "input": batch}, headers=headers)
        if r.status_code == 429 and attempt < max_retries:
            ra = r.headers.get("Retry-After")
            wait = int(ra) if (ra and ra.isdigit()) else min(2 ** attempt * 5, 60)
            print(f"  [429] backing off {wait}s (retry {attempt + 1}/{max_retries})", flush=True)
            time.sleep(wait)
            continue
        if r.status_code == 429:
            raise SystemExit("STOP: persistent 429 after retries; aborting per rate-limit policy.")
        r.raise_for_status()
        return [d["embedding"] for d in r.json()["data"]]
    raise SystemExit("STOP: exhausted retries.")


def _embed(sentences: list[str]) -> np.ndarray:
    headers = {"Authorization": f"Bearer {API_KEY}"}
    out: list[list[float]] = []
    batch_size = 32
    for i in range(0, len(sentences), batch_size):
        batch = [s if s and s.strip() else " " for s in sentences[i : i + batch_size]]
        out.extend(_post_batch(batch, headers))
        time.sleep(0.15)  # gentle throttle to stay under burst limits
    return np.asarray(out, dtype=np.float32)


def _make_encoder():
    from mteb.models.abs_encoder import AbsEncoder
    from mteb.models.model_meta import ModelMeta

    meta = ModelMeta(
        loader=lambda **kwargs: None,
        name=f"lmstudio/{MODEL}",
        revision="local",
        release_date=None,
        languages=["eng-Latn"],
        n_parameters=None,
        memory_usage_mb=None,
        max_tokens=8192,
        embed_dim=768,
        license=None,
        open_weights=True,
        public_training_code=None,
        public_training_data=None,
        framework=["API"],
        reference=None,
        similarity_fn_name="cosine",
        use_instructions=False,
        training_datasets=None,
        adapted_from=None,
        superseded_by=None,
    )

    class LMStudioEncoder(AbsEncoder):
        mteb_model_meta = meta

        def __init__(self):
            self.use_instructions = False
            self.prompts_dict = None

        def encode(self, inputs, *, task_metadata, hf_split, hf_subset, prompt_type=None, **kwargs):  # noqa: ANN001
            texts = [str(t) for batch in inputs for t in batch["text"]]
            return _embed(texts)

    return LMStudioEncoder()


def main() -> None:
    import mteb

    print(f"MTEB {mteb.__version__} | task={TASK} | model={MODEL} | endpoint={BASE}")
    tasks = mteb.get_tasks(tasks=[TASK])
    results = mteb.MTEB(tasks=tasks).run(
        _make_encoder(),
        output_folder="results/mteb",
        verbosity=2,
        encode_kwargs={"batch_size": 64},
    )
    for r in results:
        scores = getattr(r, "scores", None) or {}
        main_score = None
        for split in ("test", "validation", "train"):
            if split in scores and scores[split]:
                main_score = scores[split][0].get("main_score")
                break
        print(f"RESULT task={TASK} main_score={main_score}")


if __name__ == "__main__":
    main()
