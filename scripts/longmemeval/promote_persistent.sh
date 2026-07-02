#!/usr/bin/env bash
# Promote all LongMemEval memories from SESSION to PERSISTENT scope.
#
# WHY: menhir stamps freshly-extracted Entity nodes as scope=SESSION, and only the
# consolidation pass (lifecycle_service) promotes reinforced facts to PERSISTENT — but
# consolidation is off in benchmark mode AND it DELETES low-sharpness one-off facts, which
# is most LME answer entities. So without this step every benchmark memory stays SESSION.
#
# SESSION-scoped nodes are filtered out of recall unless include_session=True
# (recall_service.py:937), which means build_context returns empty briefs and any plain
# (non-session) recall path sees nothing. LME facts are durable knowledge the system should
# always recall, so we write them as regular memories: a blanket SESSION->PERSISTENT flip.
#
# This is idempotent and non-destructive (unlike consolidation — nothing is deleted).
# Existing recall-only A/B results are unaffected: they already use include_session=True,
# so those nodes were always visible; this only ALSO makes them visible to build_context
# and plain recall.
#
# Usage: promote_persistent.sh
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/config.sh"

NS_PREFIX="${LME_NS_PREFIX:-lme-}"
log(){ printf '[lme-promote] %s\n' "$*" >&2; }

docker ps --format '{{.Names}}' | grep -qx "${LME_NEO4J_NAME}" \
  || { log "ERROR: ${LME_NEO4J_NAME} not running"; exit 1; }

log "promoting SESSION -> PERSISTENT for namespaces prefixed '${NS_PREFIX}'..."
docker exec "${LME_NEO4J_NAME}" cypher-shell -u neo4j -p "${LME_NEO4J_PW}" --format plain \
  "MATCH (n:Entity) WHERE n.group_id STARTS WITH '${NS_PREFIX}' AND coalesce(n.scope,'SESSION')='SESSION'
   SET n.scope='PERSISTENT' RETURN count(*) AS entities_promoted;"
docker exec "${LME_NEO4J_NAME}" cypher-shell -u neo4j -p "${LME_NEO4J_PW}" --format plain \
  "MATCH ()-[r:RELATES_TO]->() WHERE r.group_id STARTS WITH '${NS_PREFIX}' AND coalesce(r.scope,'SESSION')='SESSION'
   SET r.scope='PERSISTENT' RETURN count(*) AS edges_promoted;"
log "done. LME memories are now regular (PERSISTENT) scope."
