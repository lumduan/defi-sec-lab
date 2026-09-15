#!/usr/bin/env bash
# Pin the anvil fork to Arbitrum One's CURRENT latest block, recorded in fork.env (committed).
#
# I/O
#   input : RPC_URL from .env, expanded ONLY inside a one-off anvil-service container
#   rpc   : eth_chainId, then eth_getBlockByNumber("latest"). Read-only; nothing is sent upstream.
#   output: fork.env = FORK_BLOCK_NUMBER + provenance comments (hash, L1 block, timestamp, pinned_at)
#
# Requires on the host: docker (compose v2+), jq.
# After re-pinning while the lab is running:  docker compose up -d --force-recreate
# (recreates BOTH services: anvil forks at the new block, and the foundry toolbox picks up the new
#  FORK_BLOCK_NUMBER that scripts assert against; recreating only anvil leaves the toolbox on the old pin)
set -euo pipefail
cd "$(dirname "$0")/.."

# Network errors can echo the upstream URL (API key included): mask every URL on stderr.
mask_urls() { sed -u -E 's#https?://[^[:space:]"'\''()<>]+#<url-masked>#g'; }

if [[ ! -f .env ]]; then
  echo "error: .env is missing. Create it with: cp .env.example .env   (then set RPC_URL)" >&2
  exit 1
fi

# The single-quoted program runs in the container's /bin/sh (the image entrypoint), so $RPC_URL is
# expanded there, from the service's env_file, and never by this host shell.
raw="$(
  docker compose run --rm --no-deps -T anvil '
    set -eu
    : "${RPC_URL:?RPC_URL is empty in .env}"
    cast chain-id --rpc-url "$RPC_URL"
    cast block latest --json --rpc-url "$RPC_URL"
  ' 2> >(mask_urls >&2)
)"

chain_id="$(sed -n '1p' <<<"$raw")"
block_json="$(sed -n '2,$p' <<<"$raw")"

if [[ "$chain_id" != "42161" ]]; then
  echo "error: RPC_URL reports chain id '${chain_id}'; this lab forks Arbitrum One (42161). fork.env unchanged." >&2
  exit 1
fi

# This Foundry build wraps `--json` output in an envelope (crates/cli/src/json.rs):
#   {"schema_version":1, "success":bool, "data":<block>, "errors":[...], "warnings":[...]}
# Unwrap it and fail on success=false. A bare block is accepted too, in case a later release drops it.
if jq -e 'type == "object" and has("schema_version")' >/dev/null 2>&1 <<<"$block_json"; then
  if ! jq -e '.success == true' >/dev/null 2>&1 <<<"$block_json"; then
    echo "error: cast reported failure: $(jq -r '[.errors[]?.message] | join("; ")' <<<"$block_json" 2>/dev/null | mask_urls). fork.env unchanged." >&2
    exit 1
  fi
  block_json="$(jq -c '.data' <<<"$block_json")"
fi

# Validate every field before using it: a `null` result, an error body, or an unexpected shape
# must fail loudly here instead of becoming a pin.
field() { jq -r "${1} // empty" <<<"$block_json" 2>/dev/null || true; }
number_q="$(field .number)"
hash="$(field .hash)"
timestamp_q="$(field .timestamp)"
l1_q="$(field .l1BlockNumber)"

quantity_re='^(0x[0-9a-fA-F]+|[0-9]+)$'
if [[ ! "$number_q" =~ $quantity_re || ! "$timestamp_q" =~ $quantity_re || ! "$hash" =~ ^0x[0-9a-fA-F]{64}$ ]]; then
  echo "error: unexpected 'latest block' response (number='${number_q}' timestamp='${timestamp_q}' hash='${hash}')." >&2
  echo "       Raw response (first 200 chars): $(head -c 200 <<<"$block_json" | mask_urls)" >&2
  echo "       fork.env unchanged." >&2
  exit 1
fi
[[ "$l1_q" =~ $quantity_re ]] || l1_q=""

# JSON-RPC quantities are hex strings ("0x..."); bash arithmetic converts hex and decimal alike.
number=$((number_q))
timestamp=$((timestamp_q))

{
  echo "# Fork pin, written by scripts/pin-fork-block.sh. Committed on purpose: the pin makes results reproducible."
  echo "# chain_id=42161 (Arbitrum One)"
  echo "# block_hash=${hash}"
  echo "# block_timestamp=${timestamp} ($(date -u -d "@${timestamp}" +%Y-%m-%dT%H:%M:%SZ))"
  if [[ -n "$l1_q" ]]; then
    echo "# l1_block_number=$((l1_q)) (Arbitrum: what block.number returns inside the EVM at this block)"
  fi
  echo "# pinned_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "FORK_BLOCK_NUMBER=${number}"
  echo "FORK_BLOCK_HASH=${hash}"
} > fork.env

echo "wrote fork.env:"
cat fork.env

if docker compose ps --status running --services 2>/dev/null | grep -qx anvil; then
  echo "note: the lab is still running on the previous pin. Apply with: docker compose up -d --force-recreate" >&2
fi
