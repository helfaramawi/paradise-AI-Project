#!/usr/bin/env bash
# Shared helpers for the HAQQ scripts (macOS / Linux). Source from the haqq folder.
check_docker() {
  docker info >/dev/null 2>&1 || { echo "[ERROR] Docker is not running."; return 1; }
  docker compose version >/dev/null 2>&1 || { echo "[ERROR] 'docker compose' is not available."; return 1; }
}
hq_port() {
  HQ_PORT=8090
  if [ -f .env ]; then v=$(grep -E '^HAQQ_HTTP_PORT=' .env | tail -1 | cut -d= -f2-); [ -n "$v" ] && HQ_PORT=$v; fi
}
env_value() { [ -f .env ] && grep -E "^$1=" .env | tail -1 | cut -d= -f2- || true; }
wait_db() {
  for _ in $(seq 1 40); do
    docker compose exec -T db sh -c 'pg_isready -q -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null 2>&1 && return 0
    sleep 3
  done
  echo "[ERROR] The database did not become ready. Check: docker compose logs db"; return 1
}
wait_app() {
  hq_port
  echo "Waiting for HAQQ on http://localhost:$HQ_PORT ..."
  for _ in $(seq 1 100); do
    curl -sf "http://localhost:$HQ_PORT/api/health/ready" >/dev/null 2>&1 && { echo "HAQQ is ready: http://localhost:$HQ_PORT"; return 0; }
    sleep 3
  done
  echo "[ERROR] HAQQ did not become ready. Check: docker compose logs backend"; return 1
}
