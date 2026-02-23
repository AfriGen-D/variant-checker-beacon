#!/usr/bin/env bash
set -euo pipefail

# Beacon v2 Health Monitor
# Run as cron every 5 minutes:
#   */5 * * * * /path/to/scripts/monitor_beacon.sh >> /tmp/beacon_monitor.log 2>&1
#
# Set WEBHOOK_URL env var for Slack/Discord alerts:
#   export WEBHOOK_URL="https://hooks.slack.com/services/..."

HEALTH_URL="${BEACON_HEALTH_URL:-http://localhost:8000/api/health}"
NGINX_HEALTH="${BEACON_NGINX_HEALTH:-http://localhost/health}"
DISK_WARN_THRESHOLD=85
LOG_FILE="/tmp/beacon_monitor.log"
COMPOSE_FILE="docker-compose.prod.yml"

cd "$(dirname "$0")/.."

# --- Helpers ---
ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(ts)] $*"; }

ERRORS=()

alert() {
    local msg="$1"
    ERRORS+=("$msg")
    log "ALERT: $msg"
}

send_webhook() {
    local webhook="${WEBHOOK_URL:-}"
    [ -z "$webhook" ] && return 0

    local text="🚨 *Beacon v2 Monitor Alert*\nHost: $(hostname)\nTime: $(ts)\n\n"
    for err in "${ERRORS[@]}"; do
        text+="• ${err}\n"
    done

    curl -sf -X POST "$webhook" \
        -H 'Content-Type: application/json' \
        -d "{\"text\": \"${text}\"}" >/dev/null 2>&1 || true
}

# --- Checks ---

# 1. API health
if ! curl -sf "$HEALTH_URL" >/dev/null 2>&1; then
    alert "API health check failed: $HEALTH_URL"
fi

# 2. Nginx health
if ! curl -sf "$NGINX_HEALTH" >/dev/null 2>&1; then
    alert "Nginx health check failed: $NGINX_HEALTH"
fi

# 3. Docker container status
for svc in beacon-api beacon-mongodb beacon-redis beacon-nginx; do
    status=$(docker inspect --format='{{.State.Status}}' "$svc" 2>/dev/null || echo "not_found")
    if [ "$status" != "running" ]; then
        alert "Container $svc is $status"
    fi
done

# 4. Disk usage
DISK_PCT=$(df -h / | awk 'NR==2 {gsub(/%/,""); print $5}')
if [ "$DISK_PCT" -gt "$DISK_WARN_THRESHOLD" ]; then
    alert "Disk usage at ${DISK_PCT}% (threshold: ${DISK_WARN_THRESHOLD}%)"
fi

# --- Report ---
if [ ${#ERRORS[@]} -gt 0 ]; then
    log "Health check FAILED (${#ERRORS[@]} issues)"
    send_webhook
    exit 1
else
    log "All checks passed"
    exit 0
fi
