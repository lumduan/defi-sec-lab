# 00 — First fork: Aave V3 USDC reserve on Arbitrum One, read from raw storage

> **How this note is split.**
> - §1–§6 are **evidence**: values observed on the pinned fork, each with the call that produced it, and source
>   citations at the *deployed* tags.
> - §7–§9 belong to the **owner**: prompts only.
> - Raw artifacts are in [`evidence/`](evidence/).

| | |
|---|---|
| Date | 2026-09-14 |
| Chain | Arbitrum One (chain id 42161) |
| Fork pin ([`../fork.env`](../fork.env)) | L2 block **504,982,668**; hash `0xb709093d1bb7a3b51cdecb480ad79e96af60a7aeab4ccf5313216792a11bc079`; timestamp 1789365511 (2026-09-14T05:58:31Z); L1 block 25,973,747 |
| Toolchain | `ghcr.io/foundry-rs/foundry:nightly-fc14f674bd853bc817c308a5202faa5be8df05e7@sha256:9737568248ef9d3613029c7efd4cca51a32ec52b1535248a84e07405df5b1b94` (forge/cast/anvil `1.8.2-nightly`); forge-std v1.16.2 (`bf647bd6`); solc 0.8.36 |
| Protocol | Aave V3 Arbitrum. Pool proxy `0x794a61358D6845594F94dc1DB02A252b5b4814aD` → impl `0xF05Fd3cC911b4c5E36e53c00354F645E22922C9A`, `POOL_REVISION` 11 = aave-v3-origin **v3.7.0**. aToken/vToken implementations are **v3.6.0** builds (revision 5). |
| Asset | native USDC `0xaf88d065e77c8cC2239327C5EDb3A432268e5831` (6 decimals), reserve id 12 |
| Reader | [`../script/ReadAaveReserve.s.sol`](../script/ReadAaveReserve.s.sol): **35 cross-checks OK, 0 MISMATCH** ([log](evidence/00-ReadAaveReserve-504982668.log)) |

---

## 1. Fork proof (evidence)

| Check | Input | Observed |
|---|---|---|
| Chain | `eth_chainId` → `localhost:8545` | `0xa4b1` = 42161 |
| Head = pin | `eth_blockNumber` | `0x1e196c8c` = 504,982,668 |
| Same block as upstream | `eth_getBlockByNumber(0x1e196c8c)` | hash `0xb709…c079`, identical to the hash recorded at pin time |
| L2 vs L1 block number | `ArbSys(0x64).arbBlockNumber()` vs `Multicall3(0xcA11…CA11).getBlockNumber()` | 504,982,668 (L2) vs **25,973,747** (L1): the EVM's `block.number` |
| Block time | `Multicall3.getCurrentBlockTimestamp()` | 1789365511 |
| Graceful stop flushes cache | `docker compose stop anvil` | exit code 0 in 0.77 s; `~/.foundry/cache/rpc/arbitrum/504982668/storage-<keccak(url)>.json` (33 KB) in volume `anvil-home` |
| Restart reproduces state | `docker compose up -d`, then re-read | same block hash, same base+1 word, `aToken.totalSupply()` = 175927148229223 before and after |

## 2. Address graph (evidence)

| Hop | Input | Raw output | Value |
|---|---|---|---|
| provider → Pool | `eth_call` to `0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb`, data `0x026b1d5f` (= `keccak256("getPool()")[0:4]`) | `0x000000000000000000000000794a61358d6845594f94dc1db02a252b5b4814ad` | Pool proxy `0x794a…14aD` (low 20 bytes) |
| Pool proxy → implementation | `eth_getStorageAt(pool, 0x360894a1…382bbc)` (= `keccak256("eip1967.proxy.implementation") − 1`) | `0x…f05fd3cc911b4c5e36e53c00354f645e22922c9a` | impl `0xF05F…2C9A` |
| Revision | `eth_getStorageAt(pool, 0)` / `POOL_REVISION()` | `0x…0b` / `11` | both 11 |
| Code sizes | `cast codesize` | 2,400 bytes (proxy) / 22,442 bytes (impl) | n/a |
| reserve → aToken | `_reserves[USDC]` base+4, bits 0–159 | `0x…724dc807b04555b71ed48a6896b6f41593b8c637` | aToken proxy `0x724d…C637`; its EIP-1967 slot → `0xadcb7e98a462aa2375d03145083ee68a2148f077` |
| reserve → vToken | base+6, bits 0–159 | `0x…f611aeb5013fd2c0511c9cd55c7dc5c1140741a6` | vToken proxy `0xf611…41A6`; its EIP-1967 slot → `0xc0442c25fe517ac37d6a0d485446307d97d24712` |
| rate strategy | `getReserveData().interestRateStrategyAddress` | no SLOAD observed: Pool immutable `RESERVE_INTEREST_RATE_STRATEGY` | `0x429F16dBA3B9e1900087Cbaa7b50D38Bc60fB73F` (deprecated base+7 stores the same address) |
| `stableDebtTokenAddress` (legacy field) | external call `PoolAddressesProvider.getAddress("MOCK_STABLE_DEBT")` | provider slot `0xb035f623…3cb0fcdae` = `keccak256(abi.encode(bytes32("MOCK_STABLE_DEBT"), 2))` | `0xd94112B5B62d53C9402e7A60289c6810dEF1dC9B` |

## 3. `_reserves[USDC]` in Pool storage (evidence)

### 3a. Where the struct starts
- **Declaration order at v3.7.0.**
  - [`VersionedInitializable.sol#L29`](https://github.com/aave-dao/aave-v3-origin/blob/v3.7.0/src/contracts/misc/aave-upgradeability/VersionedInitializable.sol#L29):
    slot 0 `lastInitializedRevision`, slot 1 `initializing`, slots 2–51 `uint256[50] ______gap`.
  - [`PoolStorage.sol#L21`](https://github.com/aave-dao/aave-v3-origin/blob/v3.7.0/src/contracts/protocol/pool/PoolStorage.sol#L21):
    `mapping(address => DataTypes.ReserveData) internal _reserves` → **slot 52**.
- **Preimage** `abi.encode(USDC, 52)`:
  `000000000000000000000000af88d065e77c8cc2239327c5edb3a432268e5831` ‖ `0000000000000000000000000000000000000000000000000000000000000034`
- **base** = `keccak256(preimage)` = `0xeca9b25e580a9539f66a1e310f07d98e6be14b94407490b048d1fe024e73af4f`. This equals `cast index address <USDC> 52`.
- `eth_getStorageAt(pool, 52)` = `0x0`. The mapping's own slot holds nothing.
- **Independent confirmation from execution:**
  - Both the `prestateTracer` and `vm.record`/`vm.accesses` list base+0 among the slots `getReserveData(USDC)` read.
  - Searching `p ∈ [0,300)` for `keccak256(abi.encode(USDC, p))` among those reads gives `p = 52`.

### 3b. The ten words at block 504,982,668
Struct definition: [`DataTypes.sol#L42`](https://github.com/aave-dao/aave-v3-origin/blob/v3.7.0/src/contracts/protocol/libraries/types/DataTypes.sol#L42).
Legacy ABI shape: [`#L9`](https://github.com/aave-dao/aave-v3-origin/blob/v3.7.0/src/contracts/protocol/libraries/types/DataTypes.sol#L9).

| Off | Raw word | Fields [bits] → decoded | Getter cross-check |
|---|---|---|---|
| +0 | `0x100000000000000000000103e800ee6b28000d693a4003e8850629041e781d4c` | `configuration` bitmap (see 3d) | `getReserveData().configuration` ✓ |
| +1 | `0x0000000000162d96b677fa34fe7e5e0b0000000003cea2840c4e30285542b8b5` | `liquidityIndex` [0–127] = 1178261207531790554775074997 (1.178261… ray)<br>`currentLiquidityRate` [128–255] = 26811654683114774957284875 (0.026811… ray/yr) | ✓ ✓ |
| +2 | `0x00000000001e194faa6af658ed86e4bd00000000040360a7c94b6dccbd71f3e6` | `variableBorrowIndex` [0–127] = 1242023259037647708854809574 (1.242023… ray)<br>`currentVariableBorrowRate` [128–255] = 36387303323190635207779517 (0.036387… ray/yr) | ✓ ✓ |
| +3 | `0x000000000000000000000c006aa78afb0000000000000000000000001bd5eaa8` | `deficit` [0–127] = 467004072 (467.004072 USDC)<br>`lastUpdateTimestamp` [128–167] = 1789364987<br>`id` [168–183] = 12<br>`liquidationGracePeriodUntil` [184–223] = 0<br>unused [224–255] = 0 | `getReserveDeficit` ✓; timestamp ✓; id ✓; (grace period: no legacy getter); unused = 0 ✓. Legacy `currentStableBorrowRate` = 0 is hardcoded. |
| +4 | `0x000000000000000000000000724dc807b04555b71ed48a6896b6f41593b8c637` | `aTokenAddress` [0–159]; bits 160–255 = 0 | ✓ |
| +5 | `0x0000000000000000000000000000000000000000000000000000000000000000` | deprecated (v3.2) stableDebtTokenAddress | never read by the getter |
| +6 | `0x000000000000000000000000f611aeb5013fd2c0511c9cd55c7dc5c1140741a6` | `variableDebtTokenAddress` [0–159] | ✓ |
| +7 | `0x000000000000000000000000429f16dba3b9e1900087cbaa7b50d38bc60fb73f` | deprecated (v3.4) interestRateStrategyAddress | never read; equals the Pool immutable |
| +8 | `0x000000000000000000001d0506e9ca2d00000000000000000000000fc27c355a` | `accruedToTreasury` [0–127] = 67687429466 (scaled)<br>`virtualUnderlyingBalance` [128–255] = 31907428026925 (31,907,428.026925 USDC) | ✓; `getVirtualUnderlyingBalance` ✓ |
| +9 | `0x0000000000000000000000000000000000000000000000000000000000000000` | deprecated isolationModeTotalDebt [0–127], deprecated (v3.4) virtualUnderlyingBalance [128–255] | never read; legacy `unbacked` and `isolationModeTotalDebt` are hardcoded to 0 |

### 3c. What `getReserveData(USDC)` actually read (node `prestateTracer`, [evidence](evidence/00-prestate-504982668.json))
| Contract | Slot | Is |
|---|---|---|
| Pool proxy | `0x360894a1…382bbc` | EIP-1967 implementation slot (proxy routing) |
| Pool proxy | base+0, +1, +2, +3, +4, +6, +8 | reserve words |
| PoolAddressesProvider | `0xb035f623…3cb0fcdae` | `_addresses["MOCK_STABLE_DEBT"]` (mapping at slot 2) |
| impl `0xF05F…2C9A` | none | code executed in the proxy's storage context |

Never read: +5, +7, +9. `vm.accesses` inside forge reported the same set (8 SLOAD ops over 8 unique Pool slots, 1 provider slot).

### 3d. Configuration bitmap (base+0)
Bit positions: [`ReserveConfiguration.sol#L13`](https://github.com/aave-dao/aave-v3-origin/blob/v3.7.0/src/contracts/protocol/libraries/configuration/ReserveConfiguration.sol#L13).
Every row except the last two was cross-checked against `AaveProtocolDataProvider 0x243Aa95cAC2a25651eda86e80bEe66114413c43b`.

| Field [bits] | Value |
|---|---|
| ltv [0–15] / liquidationThreshold [16–31] / liquidationBonus [32–47] | 7500 / 7800 / 10500 bps |
| decimals [48–55] | 6 |
| active [56] / frozen [57] / borrowingEnabled [58] / paused [60] / flashLoanEnabled [63] | 1 / 0 / 1 / 0 / 1 (flashLoanEnabled not cross-checked) |
| reserveFactor [64–79] | 1000 bps |
| borrowCap [80–115] / supplyCap [116–151] | 225,000,000 / 250,000,000 (whole tokens) |
| liquidationProtocolFee [152–167] | 1000 bps |
| Deprecated positions, printed not asserted | [59] = 0, [61] = 0, [62] = 0; **[168–251] = 1 (bit 168 set: lowest bit of the pre-3.2 eModeCategory field, 168–175)**; **[252] virtualAccActive = 1**; [253–255] = 0 |

## 4. Token-side storage (evidence)

| Token | Slot | Variable (declared at) | Raw value | Cross-check |
|---|---|---|---|---|
| aToken `0x724d…C637` | 54 (`0x36`) | `_totalSupply`, scaled ([IncentivizedERC20.sol#L66 @v3.6.0](https://github.com/aave-dao/aave-v3-origin/blob/v3.6.0/src/contracts/protocol/tokenization/base/IncentivizedERC20.sol#L66)) | 149310754465165 | `scaledTotalSupply()` ✓ |
| aToken | 61 (`0x3d`) | `_underlyingAsset` ([AToken.sol#L36](https://github.com/aave-dao/aave-v3-origin/blob/v3.6.0/src/contracts/protocol/tokenization/AToken.sol#L36)) | USDC | n/a |
| vToken `0xf611…41A6` | 58 (`0x3a`) | `_totalSupply`, scaled | 116019494818281 | `scaledTotalSupply()` ✓ |
| vToken | 55 (`0x37`) | `_underlyingAsset` ([DebtTokenBase.sol#L30](https://github.com/aave-dao/aave-v3-origin/blob/v3.6.0/src/contracts/protocol/tokenization/base/DebtTokenBase.sol#L30)) | USDC | n/a |

- **Same variable, different slot:** AToken inherits `VersionedInitializable, ScaledBalanceTokenBase, EIP712Base`.
  VariableDebtToken inherits `DebtTokenBase` (which brings `EIP712Base` state) *before* `ScaledBalanceTokenBase`.
- **Read sets of `totalSupply()`** (node trace and `vm.accesses` agree):
  - `aToken.totalSupply()` reads token {EIP-1967 slot, 54, 61} + Pool {EIP-1967 slot, base+1, base+3}, plus `block.timestamp`.
  - `vToken.totalSupply()` reads token {EIP-1967 slot, 58, 55} + Pool {EIP-1967 slot, base+2, base+3}, plus `block.timestamp`.

## 5. Derived numbers (evidence)

**Inputs (all raw, block 504,982,668):**
- `block.timestamp` 1789365511 − `lastUpdateTimestamp` 1789364987 → **Δt = 524 s**
- `liquidityIndex` 1178261207531790554775074997 · `currentLiquidityRate` 26811654683114774957284875
- `variableBorrowIndex` 1242023259037647708854809574 · `currentVariableBorrowRate` 36387303323190635207779517
- scaled totals: aToken 149310754465165 · vToken 116019494818281

**Formulas as written in the deployed source:**

| Step | Source |
|---|---|
| `linear = RAY + rate·Δt / SECONDS_PER_YEAR` (SECONDS_PER_YEAR = 365 days) | [MathUtils.sol#L23 @v3.7.0](https://github.com/aave-dao/aave-v3-origin/blob/v3.7.0/src/contracts/protocol/libraries/math/MathUtils.sol#L23) |
| `normalizedIncome = Δt == 0 ? liquidityIndex : linear.rayMul(liquidityIndex)` | [ReserveLogic.sol#L39](https://github.com/aave-dao/aave-v3-origin/blob/v3.7.0/src/contracts/protocol/libraries/logic/ReserveLogic.sol#L39), exposed by [Pool.sol#L515](https://github.com/aave-dao/aave-v3-origin/blob/v3.7.0/src/contracts/protocol/pool/Pool.sol#L515) |
| `x = rate·Δt / SECONDS_PER_YEAR; compounded = RAY + x + x.rayMul(x/2 + x.rayMul(x/6))` | [MathUtils.sol#L50](https://github.com/aave-dao/aave-v3-origin/blob/v3.7.0/src/contracts/protocol/libraries/math/MathUtils.sol#L50) |
| `normalizedDebt = Δt == 0 ? variableBorrowIndex : compounded.rayMul(variableBorrowIndex)` | [ReserveLogic.sol#L63](https://github.com/aave-dao/aave-v3-origin/blob/v3.7.0/src/contracts/protocol/libraries/logic/ReserveLogic.sol#L63), exposed by [Pool.sol#L522](https://github.com/aave-dao/aave-v3-origin/blob/v3.7.0/src/contracts/protocol/pool/Pool.sol#L522) |
| `aToken.totalSupply = _totalSupply.rayMulFloor(normalizedIncome)` | [AToken.sol#L142 @v3.6.0](https://github.com/aave-dao/aave-v3-origin/blob/v3.6.0/src/contracts/protocol/tokenization/AToken.sol#L142) → [TokenMath.sol#L66](https://github.com/aave-dao/aave-v3-origin/blob/v3.6.0/src/contracts/protocol/libraries/helpers/TokenMath.sol#L66) |
| `vToken.totalSupply = _totalSupply.rayMulCeil(normalizedDebt)` | [VariableDebtToken.sol#L150 @v3.6.0](https://github.com/aave-dao/aave-v3-origin/blob/v3.6.0/src/contracts/protocol/tokenization/VariableDebtToken.sol#L150) → [TokenMath.sol#L108](https://github.com/aave-dao/aave-v3-origin/blob/v3.6.0/src/contracts/protocol/libraries/helpers/TokenMath.sol#L108) |
| `rayMul` rounds half up; `rayMulFloor` floors; `rayMulCeil` ceils | [WadRayMath.sol#L64](https://github.com/aave-dao/aave-v3-origin/blob/v3.6.0/src/contracts/protocol/libraries/math/WadRayMath.sol#L64) · [#L74](https://github.com/aave-dao/aave-v3-origin/blob/v3.6.0/src/contracts/protocol/libraries/math/WadRayMath.sol#L74) · [#L85](https://github.com/aave-dao/aave-v3-origin/blob/v3.6.0/src/contracts/protocol/libraries/math/WadRayMath.sol#L85) |

**Outputs** (rebuilt in two places: host Python integer math and the forge reader):

| Quantity | Rebuilt | Protocol getter | Diff |
|---|---|---|---|
| normalizedIncome | 1178261732447870411908314374 | `getReserveNormalizedIncome` | 0 |
| **total supply** | 175927148229223 = **175,927,148.229223 USDC** | `aToken.totalSupply()` | 0 |
| normalizedDebt | 1242024009976217567048592388 | `getReserveNormalizedVariableDebt` | 0 |
| **total variable debt** | 144098998189617 = **144,098,998.189617 USDC** | `vToken.totalSupply()` | 0 |

**Rates** (stored, annual, written at `lastUpdateTimestamp`, 524 s before this block):
- supply `currentLiquidityRate` = **2.6811 % APR**
- borrow `currentVariableBorrowRate` = **3.6387 % APR**

**Adjacent raw components** (printed side by side; no relationship asserted here):

| Component | Value |
|---|---|
| aToken.totalSupply() | 175,927,148.229223 |
| vToken.totalSupply() | 144,098,998.189617 |
| virtualUnderlyingBalance | 31,907,428.026925 |
| accruedToTreasury | 67,687.429466 **scaled** units |
| deficit | 467.004072 |
| accrued over the 524 s with no transaction | supply side +78.375615, debt side +87.123514 |

## 6. Fork-fidelity observations

| # | Observation | Status |
|---|---|---|
| F1 | On this fork, EVM `block.number` = L1 block (25,973,747); the L2 block is only available via `ArbSys(0x64).arbBlockNumber()` | observed |
| F2 | Foundry stable v1.8.1 cannot `eth_call` against an Arbitrum fork head (`Excess blob gas not set`). The pinned nightly contains fixes #16514, #16465 and #16771. Move the pin to the first stable release that includes all three. | from upstream source + compare API; `eth_call` works on the nightly (observed) |
| F3 | After a fork, anvil sets each new block's timestamp to fork timestamp + wall-clock seconds since anvil started. Mining any transaction moves `block.timestamp`, which is an input to every §5 formula. | from anvil source; **not yet exercised** |
| F4 | This nightly's `cast … --json` wraps output in `{schema_version, success, data, errors, warnings}` | observed (it broke the first pin-script parse) |
| F5 | `anvil_nodeInfo` returns the upstream RPC URL including its key to any client of :8545 | from anvil source; never called in this lab |
| F6 | Reproducing this pin later needs an archive-capable RPC for any slot not already in the `anvil-home` cache | from anvil cache semantics |

---

## 7. My I/O map *(owner)*

> Prompt: for `aToken.totalSupply()`, draw the path from the output back to every input: which contract, which slot,
> which bits, which block field. Mark the inputs that change without any transaction.

> Prompt: do the same for `vToken.totalSupply()`. Where do the two graphs share inputs, and where do they differ?

## 8. State relationships I believe hold *(owner)*

> Prompt: write each relationship you believe holds between the §5 components (equation or inequality). List the
> inputs each side depends on, and which function writes each input, on which actions.

## 9. Open questions *(owner)*

-

---

## Appendix A — Reproduce

```bash
cd ~/docker/defi-sec-lab
cp .env.example .env && chmod 600 .env      # set RPC_URL: Arbitrum One (42161); archive-capable for aged pins
docker compose up -d                        # forks at FORK_BLOCK_NUMBER from fork.env (re-pin: scripts/pin-fork-block.sh)

# the full read, one command (read-only; never add --broadcast)
docker compose exec foundry forge script script/ReadAaveReserve.s.sol --fork-url anvil

# single primitives used in this note
docker compose exec foundry cast call 0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb "getPool()(address)"
docker compose exec foundry cast implementation 0x794a61358D6845594F94dc1DB02A252b5b4814aD
docker compose exec foundry cast index address 0xaf88d065e77c8cC2239327C5EDb3A432268e5831 52
docker compose exec foundry cast storage 0x794a61358D6845594F94dc1DB02A252b5b4814aD 0xeca9b25e580a9539f66a1e310f07d98e6be14b94407490b048d1fe024e73af50
docker compose exec foundry cast format-units 26811654683114774957284875 27
docker compose exec foundry cast rpc debug_traceCall \
  '{"to":"0x794a61358D6845594F94dc1DB02A252b5b4814aD","data":"0x35ea6a75000000000000000000000000af88d065e77c8cc2239327c5edb3a432268e5831"}' \
  latest '{"tracer":"prestateTracer"}'

docker compose down                         # graceful stop flushes anvil's fork cache
```

## Appendix B — Evidence files
- [`evidence/00-ReadAaveReserve-504982668.log`](evidence/00-ReadAaveReserve-504982668.log): verbatim reader output (35 OK, 0 MISMATCH).
- [`evidence/00-prestate-504982668.json`](evidence/00-prestate-504982668.json): node `prestateTracer` read sets (storage only)
  for `getReserveData(USDC)`, `aToken.totalSupply()` and `vToken.totalSupply()`.
