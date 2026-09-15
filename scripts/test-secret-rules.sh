#!/usr/bin/env bash
# Self-test the custom gitleaks rules in .gitleaks.toml: each rule must fire on a freshly generated fake
# secret, and lookalike non-secrets must stay silent. Runs inside the hooks image with the repo mounted
# read-only; the fake values only ever exist in a temp dir inside that container.
set -euo pipefail
root="$(git -C "$(dirname "$0")/.." rev-parse --show-toplevel)"
image="$("$root/scripts/hooks-image.sh")"
exec docker run --rm --user "$(id -u):$(id -g)" -v "$root:$root:ro" -w "$root" "$image" \
  python "$root/tools/hooks/selftest_rules.py" "$root/.gitleaks.toml"
