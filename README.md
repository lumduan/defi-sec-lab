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
| [`docker-compose.yml`](docker-compose.yml) | `anvil` (the fork) and `foundry` (the toolbox), each capped at 6 GB and 2 CPUs with no swap; the fork's RPC is bound to `127.0.0.1:8545`. The `learn` profile adds `learn-api` and `learn-web` (1 GB / 1 CPU each). |
| [`fork.env`](fork.env) | The committed fork pin: block number, block hash, timestamp, and L1 block. |
| [`scripts/pin-fork-block.sh`](scripts/pin-fork-block.sh) | Re-pins to the current latest block. Refuses unless the endpoint reports chain id 42161. |
| [`scripts/logs.sh`](scripts/logs.sh) | `docker compose logs` with every URL masked, because RPC URLs can carry API keys. |
| [`foundry.toml`](foundry.toml) | Pinned solc. The only RPC alias is `anvil`. Forge's fork storage caching is off. |
| [`script/ReadAaveReserve.s.sol`](script/ReadAaveReserve.s.sol) | Read-only reader for one Aave V3 reserve: raw slots → decoded fields → cross-checks against the protocol's getters → totals rebuilt from raw state. |
| [`notes/`](notes/) | The lab notebook. Entries record evidence (commands, raw words, source links) and leave the interpretation to the owner. |
| [`learn/`](learn/) | Interactive teaching page for the first entry: a Next.js app ([`learn/web`](learn/web)) and an internal-only FastAPI inspector ([`learn/api`](learn/api)), tested and built in [`app.yml`](.github/workflows/app.yml). See [Learning page](#learning-page-learn). |
| [`.gitleaks.toml`](.gitleaks.toml), [`.pre-commit-config.yaml`](.pre-commit-config.yaml), [`.secrets.baseline`](.secrets.baseline), [`.githooks/`](.githooks/), [`tools/hooks/`](tools/hooks/), [`.github/workflows/security.yml`](.github/workflows/security.yml) | Secret-scanning controls. See [Security controls](#security-controls-enforced-not-assumed). |

## How it fits together

```
 host                            docker compose project "defi-sec-lab"
 localhost:8545 ──(127.0.0.1)──▶ anvil      6g/2cpu   lazily fetches state AT the pinned block ──▶ upstream Arbitrum RPC (read-only)
 docker compose exec foundry ──▶ foundry    6g/2cpu   ETH_RPC_URL=http://anvil:8545 (talks to the fork only)
 localhost:3000 ──(127.0.0.1)──▶ learn-web  1g/1cpu   profile "learn": the teaching page
                                 learn-api  1g/1cpu   profile "learn": internal network only, no host port
```

- **Secret:** the upstream `RPC_URL` lives in a gitignored `.env`. It is passed to `anvil` and, with the `learn`
  profile, to `learn-api`. Both use it read-only.
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

## Learning page (`learn/`)

An interactive page that walks through the first entry as a four-stage flowchart. Each stage is a card; click it
to open the mechanism, every raw value, and the sources.

| Stage | Question | What it shows |
|---|---|---|
| 1 | Are we in the real bank? | Chain id 42161, the pinned block, its hash checked against `fork.env` and against the real chain, the anvil version |
| 2 | Storefront vs backroom | Proxy vs implementation code size, drawn to scale (Pool: 2,400 vs 22,442 bytes). Edge case: native USDC keeps its implementation address in the ZeppelinOS slot, not EIP-1967 |
| 3 | Open the books | `getReserveData(USDC)`: the 27-digit ray integers first, then ÷ 10²⁷, then %. LTV 75 %, liquidation threshold 78 %, liquidation bonus 105 % from the configuration bitmap |
| 4 | Read through to raw memory | `liquidityIndex` from the getter vs from the raw storage word, where two uint128 fields share one slot |

```bash
docker compose --profile learn up -d --build     # anvil + learn-api + learn-web
# browse to http://127.0.0.1:3000
docker compose --profile learn down
```

```
 browser ──127.0.0.1:3000──▶ learn-web (Next.js)   fetches server-side; the browser never talks to the API
                               │  network learn-internal: internal, isolated gateway → no host route, no published port
                               ▼
                             learn-api (FastAPI)   listens only on its learn-internal address
                               ├─ "Pinned fork" (default) ──▶ anvil at the fork.env block (+ hash check via RPC_URL)
                               └─ "Live chain"            ──▶ RPC_URL at the latest block
```

- **Read-only by construction.** The API's RPC client refuses any method outside `eth_chainId`, `eth_blockNumber`,
  `eth_getBlockByNumber`, `eth_getCode`, `eth_getStorageAt`, `eth_call`, `web3_clientVersion` (plus
  `debug_traceCall` on the fork) before anything is sent.
- **The endpoint never leaves the API.** `RPC_URL` is not logged, not returned, and is redacted from error messages.
  The tests assert this with a fake endpoint.
- **Works without the backend.** [`learn/web/data/snapshot.json`](learn/web/data/snapshot.json) is the committed
  pinned-fork inspection. If `learn-api` is down, the page renders from it and says so.

The API tests run offline: they replay RPC responses recorded from the fork, so they need no anvil and no `RPC_URL`.

```bash
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -e PYTHONDONTWRITEBYTECODE=1 -v "$PWD/learn:/learn:ro" \
  -w /learn/api python:3.14-slim sh -c 'python -m venv /tmp/venv && /tmp/venv/bin/pip install -q --require-hashes \
  -r requirements-dev.txt && /tmp/venv/bin/python -m pytest -p no:cacheprovider'
```

The snapshot, the recorded fixtures, and the tests' expected values all belong to the committed pin (block
504,982,668, the numbers in `notes/00`). If the committed pin ever moves, regenerate them together:

```bash
docker compose --profile learn exec -T learn-api python -m inspector.snapshot > learn/web/data/snapshot.json
docker compose --profile learn exec -T learn-api python -m inspector.snapshot --fixtures \
  > learn/api/tests/fixtures/rpc-fork-<block>.json     # then update the pin and expected values in learn/api/tests
```

## Toolchain pin

Foundry is pinned by image digest to `nightly-fc14f674` (2026-09-10).
- Stable v1.8.1 cannot `eth_call` against an Arbitrum fork head (`Excess blob gas not set`).
- The fixes (foundry-rs/foundry#16514, #16465, #16771) were nightly-only when this was written.
- Move the pin to the first stable release that contains all three.

## Security controls (enforced, not assumed)

This repository is public, so secret handling is enforced by tools rather than by rules in a document.
Every layer below has been tested.

| Layer | What it enforces | Can it be skipped? |
|---|---|---|
| `.gitignore` | `.env` files (except `.env.example`), key files and build output are never staged by accident. | `git add -f` |
| pre-commit hook ([`.githooks/pre-commit`](.githooks/pre-commit)) | Runs [`.pre-commit-config.yaml`](.pre-commit-config.yaml) inside a pinned container. See the list below. It fails closed if the scan can't run. | `git commit --no-verify` |
| pre-push hook ([`.githooks/pre-push`](.githooks/pre-push)) | gitleaks over every commit being pushed, which catches commits made with `--no-verify`. | `git push --no-verify` |
| CI ([`.github/workflows/security.yml`](.github/workflows/security.yml)) | On every push and pull request, including PRs from forks. See the list below. Both jobs are **required checks** on `main`. | **No.** A pull request can't merge until both pass. |

The pre-commit hook runs:
- **gitleaks** on the staged changes, using this repo's rules ([`.gitleaks.toml`](.gitleaks.toml));
- **detect-secrets** against the audited [`.secrets.baseline`](.secrets.baseline);
- guards that reject `.env` files, key files, and files over 1 MB.

The CI jobs run:
- **gitleaks** over the full git history, using a pinned and checksum-verified binary;
- every pre-commit hook on every file.

**Why custom gitleaks rules?** As of 2026-09, neither gitleaks' default rules nor GitHub push protection detect:
- RPC URLs with an embedded API key (Alchemy, Infura, QuickNode, …);
- private keys assigned to names like `DEPLOYER_PK`.

[`scripts/test-secret-rules.sh`](scripts/test-secret-rules.sh) proves each rule fires on a generated fake secret.
It also proves each rule stays silent on lookalikes: the local fork URL, anvil's public dev keys, block hashes and
addresses.

Enable the hooks in your clone. This needs Docker and installs nothing on the host:

```bash
scripts/install-hooks.sh        # sets core.hooksPath=.githooks and builds the pinned hooks image
scripts/test-secret-rules.sh    # optional: self-test the gitleaks rules
```

- **Without Docker:** `pip install pre-commit`, put gitleaks 8.30.1 on your PATH, then run `pre-commit install`.
- **When a new file legitimately trips detect-secrets:** update the baseline with
  `detect-secrets scan --baseline .secrets.baseline`, then audit it with `detect-secrets audit .secrets.baseline`,
  in the same pull request.

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
