#!/usr/bin/env bash
# Print the tag of the local hooks image, building it first if it doesn't exist yet.
# The tag is derived from the image's inputs (Dockerfile + requirements.txt), so changing either
# produces, and builds, a new image instead of silently reusing a stale one.
set -euo pipefail
root="$(git -C "$(dirname "$0")/.." rev-parse --show-toplevel)"
ctx="$root/tools/hooks"
digest="$(cat "$ctx/Dockerfile" "$ctx/requirements.txt" | sha256sum | cut -c1-12)"
tag="defi-sec-lab/hooks:$digest"
if ! docker image inspect "$tag" >/dev/null 2>&1; then
  echo "hooks-image: building $tag (first run only)..." >&2
  docker build --quiet --tag "$tag" "$ctx" >&2
fi
echo "$tag"
