#!/usr/bin/env bash
# Load the DEMO dataset (pass "reset" to recreate it). Never run on customer data.
cd "$(dirname "$0")/.." && docker compose exec -T backend python -m app.demo.seed ${1:+--reset}
