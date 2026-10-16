#!/usr/bin/env bash
# Shared helpers for the Future Mirror AI scripts (sourced, not run directly).
set -euo pipefail
OPS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$OPS_DIR/.."

fail() { echo "[FAILED] $*" >&2; exit 1; }

check_docker() {
  docker info >/dev/null 2>&1 || fail "Docker is not running. Start Docker, then try again."
  docker compose version >/dev/null 2>&1 || fail "\"docker compose\" is not available. Update Docker."
}

app_port() {
  local p=""
  [ -f .env ] && p=$(grep -E '^FM_HTTP_PORT=' .env | tail -1 | cut -d= -f2- | tr -d '\r' || true)
  echo "${p:-8080}"
}

wait_db() {
  for _ in $(seq 1 40); do
    docker compose exec -T db sh -c 'pg_isready -q -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null 2>&1 && return 0
    sleep 3
  done
  fail "The database did not become ready. Check: docker compose logs db"
}

wait_app() {
  local port; port=$(app_port)
  echo "Waiting for the app on http://localhost:$port ..."
  for _ in $(seq 1 80); do
    if curl -sf "http://localhost:$port/api/ready" >/dev/null 2>&1; then
      echo "The app is ready: http://localhost:$port"; return 0
    fi
    sleep 3
  done
  fail "The app did not become ready. Check: docker compose logs backend"
}
