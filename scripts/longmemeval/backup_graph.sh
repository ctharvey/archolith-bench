#!/usr/bin/env bash
# Backup and restore the persistent LongMemEval Neo4j graph using neo4j-admin dump/load.
#
# Usage:
#   backup_graph.sh       # dump to LME_BACKUP_DIR
#   backup_graph.sh restore <backup-file>  # restore from a dump file

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/config.sh"

log(){ printf '[lme-backup] %s\n' "$*" >&2; }
die(){ printf '[lme-backup] ERROR: %s\n' "$*" >&2; exit 1; }

mkdir -p "${LME_BACKUP_DIR}"

if [ "${1:-}" = "restore" ]; then
  BACKUP_FILE="${2:?usage: backup_graph.sh restore <backup-file>}"
  [ -f "$BACKUP_FILE" ] || die "backup file not found: $BACKUP_FILE"

  log "restoring graph from $BACKUP_FILE..."
  log "stopping ${LME_NEO4J_NAME}..."
  docker stop "${LME_NEO4J_NAME}" >/dev/null 2>&1 || true
  sleep 2

  log "loading dump into neo4j..."
  # Use docker exec neo4j-admin load to restore
  docker exec "${LME_NEO4J_NAME}" neo4j-admin load --from-path=/data/backups --database=neo4j --overwrite-existing=true <<EOF || die "restore failed"
$BACKUP_FILE
EOF
  log "starting ${LME_NEO4J_NAME}..."
  docker start "${LME_NEO4J_NAME}" >/dev/null 2>&1
  for _ in $(seq 1 60); do curl -sf "http://localhost:${LME_HTTP}" >/dev/null 2>&1 && break; sleep 2; done
  log "restore complete"
else
  log "dumping graph to ${LME_BACKUP_DIR}..."
  TS=$(date '+%Y%m%d-%H%M%S')
  DUMP_FILE="${LME_BACKUP_DIR}/lme-backup-${TS}.dump"

  # Simple approach: docker exec neo4j-admin dump
  log "creating backup (container: ${LME_NEO4J_NAME}, bolt: ${LME_BOLT})..."
  docker exec "${LME_NEO4J_NAME}" neo4j-admin dump --database=neo4j --to=/backups/dump 2>/dev/null || \
    die "dump failed — is neo4j running?"

  # Copy out of container (or use a volume mount)
  docker cp "${LME_NEO4J_NAME}:/backups/dump" "$DUMP_FILE" 2>/dev/null || \
    die "copy failed — check docker volumes"

  log "backup written to $DUMP_FILE ($(du -h "$DUMP_FILE" | cut -f1))"
  log "to restore: backup_graph.sh restore $DUMP_FILE"
fi
