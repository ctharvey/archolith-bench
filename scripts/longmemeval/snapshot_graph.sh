#!/usr/bin/env bash
# Snapshot a Neo4j data volume as a portable tarball with full provenance.
#
# Usage:
#   ./scripts/longmemeval/snapshot_graph.sh <run-id>
#
# Reads run_provenance.json from the results directory, tars the Docker volume,
# and writes a graph-snapshot.json sidecar with restore instructions.
#
# The container does NOT need to be running — this mounts the volume read-only
# in a throwaway alpine container.
#
# Restore:
#   docker volume create <vol>
#   docker run --rm -v <vol>:/data -v /path/to:/snap alpine \
#     sh -c "cd /data && tar xzf /snap/graph-snapshot.tar.gz"
#   docker run -d --name <name> -v <vol>:/data -p <bolt>:7687 -p <http>:7474 \
#     -e NEO4J_AUTH=neo4j/lmedata123 neo4j:5.26.0
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BENCH_DIR="$(git -C "${SCRIPT_DIR}" rev-parse --show-toplevel)"

RUN_ID="${1:?Usage: snapshot_graph.sh <run-id>}"
RESULTS_DIR="${BENCH_DIR}/results/lme-ku-buildout/${RUN_ID}"
PROVENANCE="${RESULTS_DIR}/run_provenance.json"
VOLUME_NAME="menhir-lme-data-${RUN_ID}"
SNAPSHOT_FILE="graph-snapshot.tar.gz"
SNAPSHOT_META="graph-snapshot.json"

die(){ printf 'ERROR: %s\n' "$*" >&2; exit 1; }

[ -d "${RESULTS_DIR}" ] || die "results dir not found: ${RESULTS_DIR}"
[ -f "${PROVENANCE}" ] || die "provenance not found: ${PROVENANCE}"
docker volume inspect "${VOLUME_NAME}" >/dev/null 2>&1 || die "volume not found: ${VOLUME_NAME}"

if [ -f "${RESULTS_DIR}/${SNAPSHOT_FILE}" ]; then
  echo "Snapshot already exists: ${RESULTS_DIR}/${SNAPSHOT_FILE}"
  echo "Delete it first to re-snapshot."
  exit 0
fi

echo "Snapshotting volume ${VOLUME_NAME}..."

# Get raw size (double-slash prevents MSYS path mangling on Windows)
export MSYS_NO_PATHCONV=1
RAW_SIZE="$(docker run --rm -v "${VOLUME_NAME}:/data:ro" alpine:latest du -sm //data | cut -f1)"

# Tar it up
docker run --rm \
  -v "${VOLUME_NAME}:/data:ro" \
  -v "${RESULTS_DIR}:/out" \
  alpine:latest \
  sh -c "tar czf //out/${SNAPSHOT_FILE} -C //data ."

COMPRESSED_SIZE="$(stat -c%s "${RESULTS_DIR}/${SNAPSHOT_FILE}" 2>/dev/null || wc -c < "${RESULTS_DIR}/${SNAPSHOT_FILE}")"
COMPRESSED_MB=$(( COMPRESSED_SIZE / 1048576 ))
SNAPSHOT_SHA="$(sha256sum "${RESULTS_DIR}/${SNAPSHOT_FILE}" | cut -d' ' -f1)"

# Read provenance fields
BENCH_PY="${BENCH_DIR}/.venv/Scripts/python.exe"
if [ ! -f "${BENCH_PY}" ]; then
  BENCH_PY="$(command -v python3 2>/dev/null || command -v python 2>/dev/null)"
fi

"${BENCH_PY}" - "${PROVENANCE}" "${RESULTS_DIR}/${SNAPSHOT_META}" \
  "${SNAPSHOT_FILE}" "${SNAPSHOT_SHA}" "${RAW_SIZE}" "${COMPRESSED_MB}" <<'PY'
import json, sys
prov = json.load(open(sys.argv[1]))
meta = {
    "snapshot_type": "neo4j-volume-tarball",
    "file": sys.argv[3],
    "sha256": sys.argv[4],
    "neo4j_version": "5.26.0",
    "size_raw_mb": int(sys.argv[5]),
    "size_compressed_mb": int(sys.argv[6]),
    "menhir_commit": prov.get("menhir_commit", "unknown"),
    "bench_commit": prov.get("bench_commit", "unknown"),
    "extract_model": prov.get("extract_model", "unknown"),
    "segmentation": prov.get("segmentation", "unknown"),
    "fixture_sha256": "bba252a302e7b257a0f7457fe97411f7de144aafd1c6b44c98a0e88ee8570907",
    "restore": (
        "docker volume create <vol> && "
        "docker run --rm -v <vol>:/data -v /path/to:/snap alpine "
        "sh -c 'cd /data && tar xzf /snap/graph-snapshot.tar.gz' && "
        "docker run -d --name <name> -v <vol>:/data -p <bolt>:7687 -p <http>:7474 "
        "-e NEO4J_AUTH=neo4j/lmedata123 neo4j:5.26.0"
    ),
}
json.dump(meta, open(sys.argv[2], "w"), indent=2)
PY

echo "Snapshot saved:"
echo "  tarball:  ${RESULTS_DIR}/${SNAPSHOT_FILE} (${COMPRESSED_MB} MB)"
echo "  metadata: ${RESULTS_DIR}/${SNAPSHOT_META}"
echo "  sha256:   ${SNAPSHOT_SHA}"
