# defi-sec-lab — Agent Operating Rules

## Purpose
Whitehat DeFi security lab. The owner supplies the domain knowledge and
decides what to investigate. The agent builds tools, monitors, harnesses,
and infrastructure that the owner directs — amplifying the owner's reach,
not replacing the owner's judgment about what to look for.

## HARD RULES — never violate
1. NEVER target mainnet or any live network for state-changing operations.
   All tests, PoCs, and exploits run against the LOCAL fork only
   (anvil on localhost:8545).
2. NEVER put a real private key anywhere in the repo. Use anvil's default
   test keys only. If a real key ever seems necessary, STOP and ask.
3. NEVER broadcast a transaction to a public network. `cast send` and
   `forge script --broadcast` against any non-local RPC are forbidden.
4. Resource limits (memory, cpu) in docker-compose must never be removed
   or raised without the owner asking.

## Working style
- Explain the mechanism before writing code. Show me the I/O and the state
  changes; don't hand me black-box results.
- When building analysis tooling (monitors, scanners, invariant harnesses,
  state-diff viewers), that's the primary job — build it well and make it
  reusable. The owner interprets the output and decides what's a finding.
- When writing a PoC, stop at "proof on fork." Never extend toward a
  deployable or mainnet-ready version.
- Prefer state diffs (storage before/after) over summarized results.
- Pin the fork block number for reproducibility.

## Escalate to owner before
- Any operation touching a real wallet, real key, or mainnet.
- Installing anything outside the container.
- Any request that reads like "make this work against the real protocol."
