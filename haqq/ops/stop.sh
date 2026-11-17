#!/usr/bin/env bash
cd "$(dirname "$0")/.." && docker compose stop && echo "HAQQ stopped; data kept."
