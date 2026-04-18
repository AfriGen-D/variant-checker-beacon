#!/usr/bin/env bash
set -euo pipefail

# Beacon v2 Production Deployment Script
# Usage: ./scripts/deploy.sh [--pull-only]
#   --pull-only: Pull images only (for CI/CD mode, skip git pull + build)

COMPOSE_FILE="compose/docker-compose.prod.yml"
HEALTH_URL="http://localhost:8000/api/health"
HEALTH_TIMEOUT=60
DISK_WARN_THRESHOLD=85

cd "$(dirname "$0")/.."

# --- Helpers ---
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
die() { log "ERROR: $*" >&2; exit 1; }

# --- Pre-flight checks ---
log "Running pre-flight checks..."

# Check disk usage
DISK_PCT=$(df -h / | awk 'NR==2 {gsub(/%/,""); print $5}')
if [ "$DISK_PCT" -gt "$DISK_WARN_THRESHOLD" ]; then
    log "WARNING: Disk usage at ${DISK_PCT}% (threshold: ${DISK_WARN_THRESHOLD}%)"
fi

# Check .env.production exists
[ -f .env.production ] || die ".env.production not found. Copy .env.example and fill in values."

# Check docker compose is available
command -v docker >/dev/null 2>&1 || die "docker not found"
docker compose version >/dev/null 2>&1 || die "docker compose plugin not found"

# --- Deploy ---
PULL_ONLY=false
if [ "${1:-}" = "--pull-only" ]; then
    PULL_ONLY=true
fi

if [ "$PULL_ONLY" = true ]; then
    log "Pull-only mode: pulling images..."
    docker compose -f "$COMPOSE_FILE" pull
else
    log "Pulling latest code..."
    git pull --ff-only || die "git pull failed — resolve conflicts locally and re-deploy"

    log "Building containers..."
    docker compose -f "$COMPOSE_FILE" build
fi

log "Starting services..."
docker compose -f "$COMPOSE_FILE" up -d

# --- Health check ---
log "Waiting for API health (timeout: ${HEALTH_TIMEOUT}s)..."
elapsed=0
while [ $elapsed -lt $HEALTH_TIMEOUT ]; do
    if curl -sf "$HEALTH_URL" >/dev/null 2>&1; then
        log "API is healthy!"
        break
    fi
    sleep 2
    elapsed=$((elapsed + 2))
done

if [ $elapsed -ge $HEALTH_TIMEOUT ]; then
    log "WARNING: API did not become healthy within ${HEALTH_TIMEOUT}s"
    log "Container status:"
    docker compose -f "$COMPOSE_FILE" ps
    log "Recent API logs:"
    docker compose -f "$COMPOSE_FILE" logs --tail=20 beacon-api
    exit 1
fi

# --- Cleanup ---
log "Pruning dangling images..."
docker image prune -f >/dev/null 2>&1 || true

log "Deployment complete. Container status:"
docker compose -f "$COMPOSE_FILE" ps
