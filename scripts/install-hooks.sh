#!/usr/bin/env bash
# Enable this repo's git hooks in the current clone:
#   1. point git at the committed .githooks/ (repo-local config; nothing installed on the host)
#   2. build the pinned hooks image (gitleaks + pre-commit + detect-secrets)
#   3. pre-install the pre-commit hook environments into the cache volume
# Hooks are a local convenience. CI (.github/workflows/security.yml) is the gate that cannot be skipped.
set -euo pipefail
root="$(git -C "$(dirname "$0")/.." rev-parse --show-toplevel)"
git -C "$root" config core.hooksPath .githooks
image="$("$root/scripts/hooks-image.sh")"
docker run --rm --user "$(id -u):$(id -g)" -v "$root:$root" -w "$root" \
  -v defi-sec-lab-precommit-cache:/cache "$image" pre-commit install-hooks
echo "hooks enabled: core.hooksPath=.githooks (pre-commit, pre-push) using $image"
