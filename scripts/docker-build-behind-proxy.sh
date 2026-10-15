#!/usr/bin/env bash
# Builds the images in environments where outbound traffic goes through an HTTP proxy
# with a private CA (e.g. corporate networks or sandboxes). Usage:
#   CA_BUNDLE=/path/to/ca.crt ./scripts/docker-build-behind-proxy.sh
set -euo pipefail
cd "$(dirname "$0")/.."
CA="${CA_BUNDLE:-}"
SECRET=()
[ -n "$CA" ] && SECRET=(--secret "id=extra_ca,src=$CA")
for svc in backend frontend; do
  docker build --network host \
    --build-arg HTTP_PROXY="${HTTP_PROXY:-${http_proxy:-}}" --build-arg HTTPS_PROXY="${HTTPS_PROXY:-${https_proxy:-}}" \
    --build-arg http_proxy="${HTTP_PROXY:-${http_proxy:-}}" --build-arg https_proxy="${HTTPS_PROXY:-${https_proxy:-}}" \
    --build-arg NO_PROXY="${NO_PROXY:-localhost,127.0.0.1}" "${SECRET[@]}" \
    -t "future-mirror-$svc" "./$svc"
done
echo "Built future-mirror-backend and future-mirror-frontend. Start with: docker compose up -d"
