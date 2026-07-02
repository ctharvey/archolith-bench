#!/usr/bin/env bash
# Stand up menhir-frontier on the LME graph and probe recall ranking for one question.
set -uo pipefail
ARCH=/c/Users/thron/IdeaProjects/projects/archolith
SRC="$ARCH/menhir-frontier"
BIN="$SRC/.venv/Scripts/menhir"
PY="$ARCH/menhir/.venv/Scripts/python.exe"
PORT=8104; URL="http://localhost:$PORT"
NS="lme-gpt4_2655b836"
Q="What was the first issue I had with my new car after its first service?"

KEY="$("$PY" - "$ARCH/menhir/.env" OPENAI_API_KEY <<'PY'
import sys; from dotenv import dotenv_values; print(dotenv_values(sys.argv[1]).get(sys.argv[2],""))
PY
)"
PID=""
cleanup(){ [ -n "$PID" ] && kill "$PID" 2>/dev/null || true; }
trap cleanup EXIT

export PYTHONPATH="$SRC/src"
EMPTY="$(mktemp)"; export ENV_FILE="$EMPTY"
export MENHIR_BENCHMARK_MODE=1 MENHIR_API_HOST=127.0.0.1 MENHIR_API_PORT="$PORT"
export MENHIR_LOG_DIR="$(mktemp -d)"
export OTEL_SDK_DISABLED=true LANGFUSE_TRACING_ENABLED=false LANGFUSE_PUBLIC_KEY="" LANGFUSE_SECRET_KEY="" LANGFUSE_HOST=""
export MENHIR_OPERATOR_KEY="" MENHIR_AGENT_KEY="" MENHIR_READONLY_KEY="" MENHIR_API_KEY=""
export NEO4J_URI="bolt://localhost:7689" NEO4J_USER="neo4j" NEO4J_PASSWORD="lmedata123" NEO4J_DATABASE="neo4j"
export GRAPHITI_EMBED_PROVIDER="openai" MEMORY_GRAPHITI_EMBED_PROVIDER="openai"
export OPENAI_API_KEY="$KEY" OPENAI_EMBED_MODEL="text-embedding-3-small"

( cd "$SRC" && "$BIN" serve --port "$PORT" ) >/dev/null 2>&1 & PID=$!
until curl -sf "$URL/api/health" >/dev/null 2>&1; do sleep 2; done
echo "menhir up on $PORT"

for LIM in 10 50; do
  echo "======== recall limit=$LIM (preset=knowledge, include_session=true) ========"
  curl -s -X POST "$URL/api/recall" -H 'content-type: application/json' \
    -d "{\"query\":\"$Q\",\"namespace\":\"$NS\",\"limit\":$LIM,\"include_session\":true,\"preset\":\"knowledge\"}" \
    -o "$MENHIR_LOG_DIR/resp_$LIM.json" -w "HTTP %{http_code} bytes=%{size_download}\n"
  "$PY" - "$MENHIR_LOG_DIR/resp_$LIM.json" <<'PY'
import sys,json
d=json.load(open(sys.argv[1],encoding="utf-8"))
res=d.get("results",[])
print("candidates_evaluated:",d.get("candidates_evaluated"),"| returned:",len(res))
gps_rank=None
for i,r in enumerate(res,1):
    blob=((r.get("content") or "")+" "+(r.get("name") or "")).lower()
    is_gps="gps" in blob or "dealership" in blob
    if is_gps and gps_rank is None: gps_rank=i
    print(f'{i:2d}. {r.get("final_score"):.3f} name={r.get("name")!r} content={r.get("content")!r}{"   <<< ANSWER NODE" if is_gps else ""}')
print(">>> gold GPS/dealership fact first appears at rank:", gps_rank)
PY
done
