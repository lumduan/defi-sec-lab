# defi-sec-lab

A whitehat DeFi security lab built around a **pinned, local fork of Arbitrum One**, with Foundry (anvil, forge,
cast) running in Docker. The work here reads live protocol state down to **raw storage slots**. The goal is to
understand the mechanism and the input/output relationships behind a number, not to trust the summarized number.

> **Local fork only.** Nothing in this repository sends transactions to a public network, and nothing needs a real
> private key. The operating rules are in [`AGENTS.md`](AGENTS.md).

## What's in the repo

| Path | Purpose |
|---|---|
| [`AGENTS.md`](AGENTS.md) | Operating rules for humans and coding agents: hard safety rules and working style. [`CLAUDE.md`](CLAUDE.md) imports it for Claude Code. |
| [`docker-compose.yml`](docker-compose.yml) | `anvil` (the fork) and `foundry` (the toolbox). Each container is capped at 6 GB and 2 CPUs with no swap; the fork's RPC is bound to `127.0.0.1:8545`. |
| [`fork.env`](fork.env) | The committed fork pin: block number, block hash, timestamp, and L1 block. |
| [`scripts/pin-fork-block.sh`](scripts/pin-fork-block.sh) | Re-pins to the current latest block. Refuses unless the endpoint reports chain id 42161. |
| [`scripts/logs.sh`](scripts/logs.sh) | `docker compose logs` with every URL masked, because RPC URLs can carry API keys. |
| [`foundry.toml`](foundry.toml) | Pinned solc. The only RPC alias is `anvil`. Forge's fork storage caching is off. |
| [`script/ReadAaveReserve.s.sol`](script/ReadAaveReserve.s.sol) | Read-only reader for one Aave V3 reserve: raw slots → decoded fields → cross-checks against the protocol's getters → totals rebuilt from raw state. |
| [`notes/`](notes/) | The lab notebook. Entries record evidence (commands, raw words, source links) and leave the interpretation to the owner. |

## How it fits together

```
 host                            docker compose project "defi-sec-lab"
 localhost:8545 ──(127.0.0.1)──▶ anvil    6g/2cpu   lazily fetches state AT the pinned block ──▶ upstream Arbitrum RPC (read-only)
 docker compose exec foundry ──▶ foundry  6g/2cpu   ETH_RPC_URL=http://anvil:8545 (talks to the fork only)
```

- **Secret:** the upstream `RPC_URL` lives in a gitignored `.env` and is passed only to the anvil container.
- **Pin:** the fork is pinned to a block number in `fork.env`, so every read can be reproduced.
- **Cache:** anvil caches the state it fetches in a Docker volume and writes it to disk on a graceful stop
  (`docker compose stop` / `down`).

## Quick start

You need Docker with Compose v2, `jq` (for the pin script), and an **Arbitrum One** RPC endpoint.

```bash
git clone --recurse-submodules https://github.com/lumduan/defi-sec-lab.git
cd defi-sec-lab
cp .env.example .env && chmod 600 .env      # set RPC_URL (Arbitrum One, chain id 42161). Never commit it.
```

Then choose which block to fork:

```bash
# Option A: reproduce the committed pin (block 504982668). Needs an archive-capable endpoint.
docker compose up -d

# Option B: pin to the current latest block instead. Works with any node.
./scripts/pin-fork-block.sh && docker compose up -d --force-recreate
```

Run the reader (read-only; never add `--broadcast`), and stop the lab when done:

```bash
docker compose exec foundry forge script script/ReadAaveReserve.s.sol --fork-url anvil

# any other reserve:
docker compose exec foundry forge script script/ReadAaveReserve.s.sol --fork-url anvil --sig "read(address)" <asset>

docker compose down                          # graceful stop: flushes anvil's fork cache
```

- Cloned without `--recurse-submodules`? Run `git submodule update --init`.
- With Option B the values will differ from `notes/00` (different block). The reader's cross-checks should still pass.
  - If Aave has upgraded the Pool past revision 11, the reader prints a warning: its layout facts were verified
    for v3.7.0.

## First entry: Aave V3 USDC on Arbitrum ([`notes/00`](notes/00-first-fork.md))

At block 504,982,668 the native-USDC reserve reads as follows:

| Number | Where it comes from |
|---|---|
| Total supply: 175,927,148.23 USDC | Not stored. Computed at read time: aToken slot 54 (scaled total) × normalizedIncome(liquidityIndex, rate, lastUpdateTimestamp, `block.timestamp`) |
| Total variable debt: 144,098,998.19 USDC | Not stored. vToken slot 58 (scaled total) × normalizedDebt (compounded, rounded up) |
| Supply 2.68 % / borrow 3.64 % APR | Pool proxy storage: `_reserves[USDC]` words base+1 / base+2, high 128 bits, as of the last state-changing action |

Mechanisms the note shows with evidence:
- **Proxies.** The Pool's storage lives at the proxy address, and its code is located through the EIP-1967
  implementation slot.
- **Mapping slots.** `_reserves` is declared at slot 52, so USDC's struct starts at `keccak256(abi.encode(USDC, 52))`.
  - This is confirmed from the source.
  - It is also confirmed from the SLOADs the getter actually performs, using `debug_traceCall` with `prestateTracer`
    and forge's `vm.accesses`.
- **Packing.** Small fields share 256-bit words. Every field was sliced out of the raw words; 35/35 cross-checks
  against the protocol's getters pass.
- **Derived totals.** Both totals were rebuilt from raw slots with Aave's own rounding rules and match exactly (diff 0).
- **Arbitrum specifics.** Inside the EVM, `block.number` is the L1 block; the L2 block number comes from the `ArbSys`
  precompile.

## Toolchain pin

Foundry is pinned by image digest to `nightly-fc14f674` (2026-09-10).
- Stable v1.8.1 cannot `eth_call` against an Arbitrum fork head (`Excess blob gas not set`).
- The fixes (foundry-rs/foundry#16514, #16465, #16771) were nightly-only when this was written.
- Move the pin to the first stable release that contains all three.

## Safety notes for anyone using this repo

- **Keep `.env` out of git** (it is ignored) and never paste the endpoint anywhere.
  - anvil's `anvil_nodeInfo` returns the full fork URL to any client that can reach port 8545, so keep that port
    on loopback.
  - Read logs through `scripts/logs.sh`: RPC error messages can echo the URL.
- **Nothing goes to a live network.** Don't add public RPC endpoints, `--broadcast`, or real keys. PoCs stop at
  "proof on fork".
- **Responsible disclosure.** Anything that looks like a vulnerability in a live protocol goes privately to that
  protocol's security contact or bug bounty, never into a public issue or this repository.

## License

[MIT](LICENSE).
- `lib/forge-std` is a git submodule under its own license (Apache-2.0 OR MIT).
- Aave sources are cited by link, not vendored.
