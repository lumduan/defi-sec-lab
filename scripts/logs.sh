#!/usr/bin/env bash
# `docker compose logs` with every http(s) URL masked.
# Why: anvil and cast network errors can echo the upstream RPC URL, API key included.
# Read the lab's logs only through this script.
# Usage: scripts/logs.sh [docker compose logs args]     e.g.  scripts/logs.sh --tail 50 anvil
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose logs "$@" 2>&1 | sed -u -E 's#https?://[^[:space:]"'\''()<>]+#<url-masked>#g'
