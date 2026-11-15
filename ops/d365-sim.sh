#!/usr/bin/env bash
# Start the local Dynamics 365 F&O simulator (Arabic test data) and connect Future Mirror to it.
#   ops/d365-sim.sh         start, configure the "Dynamics 365 F&O" connection and test it
#   ops/d365-sim.sh stop    stop the simulator only
# See docs/D365_FO_TESTING.md.
source "$(dirname "$0")/_common.sh"
check_docker
if [ "${1:-}" = "stop" ]; then
  docker compose --profile d365sim stop d365fo-sim
  echo "Simulator stopped. Future Mirror keeps running."
  exit 0
fi
add_env() {  # set KEY=VALUE in .env unless KEY already has a value there
  touch .env
  grep -qE "^$1=[^[:space:]]" .env && return 0
  grep -vE "^$1=" .env > .env.tmp || true
  cat .env.tmp > .env && rm -f .env.tmp
  [ -s .env ] && [ "$(tail -c1 .env)" != "" ] && echo >> .env
  echo "$1=$2" >> .env
  echo "Set $1 in .env"
}
add_env FM_D365_FO_CLIENT_SECRET fm-sim-secret-2026
add_env FM_D365_CA_BUNDLE /certs/d365sim/ca.pem
echo "Starting Future Mirror AI with the Dynamics 365 F&O simulator ..."
docker compose --profile d365sim up -d --build
wait_app
sim_port=8443
[ -f .env ] && p=$(grep -E '^FM_D365_SIM_PORT=' .env | tail -1 | cut -d= -f2- | tr -d '\r') && [ -n "$p" ] && sim_port=$p
echo "Connecting Future Mirror to the simulator ..."
docker compose --profile d365sim run --rm --no-deps d365fo-sim python -m d365fo_sim.configure_fm \
  || fail "Configuring the connection failed (see the message above)."
echo
echo "Done. Test data in the browser: https://localhost:$sim_port (accept the certificate warning)."
echo "In Future Mirror open Data Connections > Dynamics 365 Finance & Operations and press Sync."
