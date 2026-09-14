// SPDX-License-Identifier: MIT
pragma solidity 0.8.36;

import {Script, console2} from "forge-std/Script.sol";

// -----------------------------------------------------------------------------------------------
// Minimal interfaces: only what this reader calls (signatures from aave-v3-origin v3.7.0).
// -----------------------------------------------------------------------------------------------

interface IPoolAddressesProvider {
    function getPool() external view returns (address);
}

interface IPool {
    /// @dev The ABI shape getReserveData() returns. It is NOT the storage layout (see section 4).
    struct ReserveDataLegacy {
        uint256 configuration; // ReserveConfigurationMap{uint256 data}: ABI-identical to a bare uint256
        uint128 liquidityIndex;
        uint128 currentLiquidityRate;
        uint128 variableBorrowIndex;
        uint128 currentVariableBorrowRate;
        uint128 currentStableBorrowRate;
        uint40 lastUpdateTimestamp;
        uint16 id;
        address aTokenAddress;
        address stableDebtTokenAddress;
        address variableDebtTokenAddress;
        address interestRateStrategyAddress;
        uint128 accruedToTreasury;
        uint128 unbacked;
        uint128 isolationModeTotalDebt;
    }

    function getReserveData(address asset) external view returns (ReserveDataLegacy memory);
    function getReserveNormalizedIncome(address asset) external view returns (uint256);
    function getReserveNormalizedVariableDebt(address asset) external view returns (uint256);
    function getReserveDeficit(address asset) external view returns (uint256);
    function getVirtualUnderlyingBalance(address asset) external view returns (uint128);
    function POOL_REVISION() external view returns (uint256);
}

interface IScaledBalanceToken {
    function scaledTotalSupply() external view returns (uint256);
    function totalSupply() external view returns (uint256);
}

interface IPoolDataProvider {
    function getReserveConfigurationData(address asset)
        external
        view
        returns (
            uint256 decimals,
            uint256 ltv,
            uint256 liquidationThreshold,
            uint256 liquidationBonus,
            uint256 reserveFactor,
            bool usageAsCollateralEnabled,
            bool borrowingEnabled,
            bool stableBorrowRateEnabled,
            bool isActive,
            bool isFrozen
        );
    function getReserveCaps(address asset) external view returns (uint256 borrowCap, uint256 supplyCap);
    function getPaused(address asset) external view returns (bool isPaused);
    function getLiquidationProtocolFee(address asset) external view returns (uint256);
}

interface IArbSys {
    function arbBlockNumber() external view returns (uint256);
}

/// @title ReadAaveReserve
/// @notice READ-ONLY state reader for one Aave V3 reserve on the LOCAL Arbitrum fork.
///         Walks provider -> pool -> reserve, observes which storage slots the getters read, dumps
///         the raw 32-byte words, decodes every field, cross-checks each against the protocol's own
///         getters, and rebuilds total supply / total variable debt from raw slots + block.timestamp.
/// @dev    Never broadcasts: there is no vm.broadcast / vm.startBroadcast anywhere in this file.
///         Run inside the foundry container:
///           forge script script/ReadAaveReserve.s.sol --fork-url anvil
///           forge script script/ReadAaveReserve.s.sol --fork-url anvil --sig "read(address)" <asset>
contract ReadAaveReserve is Script {
    // Root of Aave V3 on Arbitrum One. Every other Aave address is walked on-chain from here.
    address internal constant PROVIDER = 0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb;
    // AaveProtocolDataProvider: used only to cross-check the configuration bitmap decode.
    address internal constant DATA_PROVIDER = 0x243Aa95cAC2a25651eda86e80bEe66114413c43b;
    address internal constant USDC = 0xaf88d065e77c8cC2239327C5EDb3A432268e5831; // native (Circle) USDC
    address internal constant ARBSYS = address(0x64);
    uint256 internal constant ARBITRUM_ONE = 42161;

    // keccak256("eip1967.proxy.implementation") - 1
    bytes32 internal constant EIP1967_IMPL_SLOT = 0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc;

    // Layout facts from source: aave-v3-origin v3.7.0 (Pool) and v3.6.0 (tokens). The script re-derives
    // or re-checks each one against the chain and reports disagreement instead of trusting it.
    uint256 internal constant VERIFIED_POOL_REVISION = 11;
    uint256 internal constant RESERVES_MAPPING_SLOT = 52; // VersionedInitializable uses 0..51, then PoolStorage._reserves
    uint256 internal constant ATOKEN_TOTAL_SUPPLY_SLOT = 54; // IncentivizedERC20._totalSupply inside AToken
    uint256 internal constant ATOKEN_UNDERLYING_SLOT = 61; // AToken._underlyingAsset
    uint256 internal constant VTOKEN_TOTAL_SUPPLY_SLOT = 58; // same variable; DebtTokenBase state comes first
    uint256 internal constant VTOKEN_UNDERLYING_SLOT = 55; // DebtTokenBase._underlyingAsset
    uint256 internal constant PROVIDER_ADDRESSES_SLOT = 2; // PoolAddressesProvider._addresses (bytes32 => address)

    // WadRayMath / MathUtils constants.
    uint256 internal constant RAY = 1e27;
    uint256 internal constant HALF_RAY = 0.5e27;
    uint256 internal constant SECONDS_PER_YEAR = 365 days;

    uint256 internal passed;
    uint256 internal mismatched;

    struct Ctx {
        IPool pool;
        address asset;
        bytes32 base; // keccak256(abi.encode(asset, RESERVES_MAPPING_SLOT))
        address aToken;
        address vToken;
        uint256 decimals;
        uint128 liquidityIndex;
        uint128 liquidityRate;
        uint128 variableBorrowIndex;
        uint128 variableBorrowRate;
        uint40 lastUpdateTimestamp;
        uint128 deficit;
        uint128 accruedToTreasury;
        uint128 virtualUnderlyingBalance;
        uint256 totalSupply;
        uint256 totalDebt;
    }

    function run() external {
        read(USDC);
    }

    function read(address asset) public {
        Ctx memory c;
        c.asset = asset;
        _context();
        _addressGraph(c);
        _observeGetterReads(c);
        _reserveWordsIndexesAndRates(c);
        _reserveWordsPackedAndAddresses(c);
        _configurationParams(c);
        _configurationFlagsAndCaps(c);
        _supply(c);
        _debt(c);
        _ratesAndComponents(c);
        _header("SUMMARY");
        _log(string.concat("cross-checks: ", _u(passed), " OK, ", _u(mismatched), " MISMATCH"));
        _log("read-only: nothing was broadcast");
    }

    // ------------------------------------------------------------------------------------------
    // 1. Context
    // ------------------------------------------------------------------------------------------
    function _context() internal {
        _header("1. CONTEXT: which chain, which block");
        uint256 l2 = IArbSys(ARBSYS).arbBlockNumber();
        _log(string.concat("block.chainid                        = ", _u(block.chainid)));
        _log(string.concat("ArbSys(0x64).arbBlockNumber() [L2]   = ", _u(l2)));
        _log(string.concat("block.number [EVM view = L1 block]   = ", _u(block.number)));
        _log(string.concat("block.timestamp                      = ", _u(block.timestamp)));
        require(block.chainid == ARBITRUM_ONE, "not an Arbitrum One fork");
        uint256 pinned = vm.envOr("FORK_BLOCK_NUMBER", uint256(0));
        if (pinned == 0) {
            _log("FORK_BLOCK_NUMBER not set in the environment: pin NOT asserted");
        } else {
            _check("fork head (L2) == fork.env FORK_BLOCK_NUMBER", l2, pinned);
        }
    }

    // ------------------------------------------------------------------------------------------
    // 2. Address graph + proxy
    // ------------------------------------------------------------------------------------------
    function _addressGraph(Ctx memory c) internal {
        _header("2. ADDRESS GRAPH: provider -> pool proxy -> implementation");
        c.pool = IPool(IPoolAddressesProvider(PROVIDER).getPool());
        address impl = address(uint160(uint256(vm.load(address(c.pool), EIP1967_IMPL_SLOT))));
        uint256 revisionInStorage = uint256(vm.load(address(c.pool), bytes32(0)));
        uint256 revisionInCode = c.pool.POOL_REVISION();
        _log(string.concat("PoolAddressesProvider.getPool()        = ", _a(address(c.pool))));
        _log(string.concat("vm.load(pool, EIP-1967 impl slot)      = ", _a(impl)));
        _log(string.concat("code size: proxy ", _u(address(c.pool).code.length), " bytes, implementation ", _u(impl.code.length), " bytes"));
        _log(string.concat("POOL_REVISION() (constant in impl code) = ", _u(revisionInCode), " -> aave-v3-origin ", _release(revisionInCode)));
        _check("slot 0 lastInitializedRevision == POOL_REVISION()", revisionInStorage, revisionInCode);
        if (revisionInCode != VERIFIED_POOL_REVISION) {
            _log("WARNING: layout facts in this script were verified for revision 11 (v3.7.0). Re-verify before trusting decoded fields.");
        }
    }

    // ------------------------------------------------------------------------------------------
    // 3. Observe the getter's storage reads, derive the mapping slot from evidence
    // ------------------------------------------------------------------------------------------
    function _observeGetterReads(Ctx memory c) internal {
        _header("3. OBSERVE: which storage slots does getReserveData(asset) read? (vm.record / vm.accesses)");
        vm.record();
        IPool.ReserveDataLegacy memory r = c.pool.getReserveData(c.asset);
        (bytes32[] memory poolOps,) = vm.accesses(address(c.pool));
        (bytes32[] memory providerOps,) = vm.accesses(PROVIDER);
        vm.stopRecord();

        // Which mapping slot p makes keccak256(abi.encode(asset, p)) one of the slots that was read?
        uint256 p = type(uint256).max;
        for (uint256 i = 0; i < 300; i++) {
            if (_contains(poolOps, keccak256(abi.encode(c.asset, i)))) {
                p = i;
                break;
            }
        }
        require(p != type(uint256).max, "no mapping slot in [0,300) matches the observed reads");
        c.base = keccak256(abi.encode(c.asset, p));
        _check("_reserves mapping slot derived from reads == source layout (52)", p, RESERVES_MAPPING_SLOT);
        _log(string.concat("base = keccak256(abi.encode(asset, ", _u(p), ")) = ", _b32(c.base)));

        bytes32[] memory poolSlots = _unique(poolOps);
        _log(string.concat("Pool proxy: ", _u(poolOps.length), " SLOAD ops over ", _u(poolSlots.length), " unique slots"));
        for (uint256 i = 0; i < poolSlots.length; i++) {
            _log(string.concat("  ", _b32(poolSlots[i]), " <- ", _poolSlotLabel(c.base, poolSlots[i])));
            _log(string.concat("    = ", _b32(vm.load(address(c.pool), poolSlots[i]))));
        }
        bytes32[] memory providerSlots = _unique(providerOps);
        bytes32 mockKey = keccak256(abi.encode(bytes32("MOCK_STABLE_DEBT"), PROVIDER_ADDRESSES_SLOT));
        _log(string.concat("PoolAddressesProvider: ", _u(providerOps.length), " SLOAD ops over ", _u(providerSlots.length), " unique slots"));
        for (uint256 i = 0; i < providerSlots.length; i++) {
            string memory label = providerSlots[i] == mockKey ? string('_addresses["MOCK_STABLE_DEBT"] (mapping slot 2)') : string("unlabelled");
            _log(string.concat("  ", _b32(providerSlots[i]), " <- ", label));
            _log(string.concat("    = ", _b32(vm.load(PROVIDER, providerSlots[i]))));
        }
        _log(string.concat("interestRateStrategyAddress = ", _a(r.interestRateStrategyAddress), " <- no SLOAD: immutable in implementation bytecode"));

        c.aToken = r.aTokenAddress;
        c.vToken = r.variableDebtTokenAddress;
    }

    // ------------------------------------------------------------------------------------------
    // 4. Raw words of _reserves[asset], decoded field by field, each checked against a getter
    // ------------------------------------------------------------------------------------------
    function _reserveWordsIndexesAndRates(Ctx memory c) internal {
        _header("4. RAW WORDS of _reserves[asset] (base+0..base+9), decoded and cross-checked");
        IPool.ReserveDataLegacy memory r = c.pool.getReserveData(c.asset);

        uint256 w = _logWord(c, 0, "configuration bitmap (decoded in section 5)");
        _check("  configuration                  [0-255]", w, r.configuration);

        w = _logWord(c, 1, "liquidityIndex [0-127] | currentLiquidityRate [128-255]");
        c.liquidityIndex = uint128(w);
        c.liquidityRate = uint128(w >> 128);
        _check("  liquidityIndex (ray)           [0-127]", c.liquidityIndex, r.liquidityIndex);
        _check("  currentLiquidityRate (ray/yr)  [128-255]", c.liquidityRate, r.currentLiquidityRate);

        w = _logWord(c, 2, "variableBorrowIndex [0-127] | currentVariableBorrowRate [128-255]");
        c.variableBorrowIndex = uint128(w);
        c.variableBorrowRate = uint128(w >> 128);
        _check("  variableBorrowIndex (ray)      [0-127]", c.variableBorrowIndex, r.variableBorrowIndex);
        _check("  currentVariableBorrowRate      [128-255]", c.variableBorrowRate, r.currentVariableBorrowRate);

        w = _logWord(c, 3, "deficit [0-127] | lastUpdateTimestamp [128-167] | id [168-183] | liquidationGracePeriodUntil [184-223] | unused [224-255]");
        c.deficit = uint128(w);
        c.lastUpdateTimestamp = uint40(w >> 128);
        _check("  deficit vs getReserveDeficit() [0-127]", c.deficit, c.pool.getReserveDeficit(c.asset));
        _check("  lastUpdateTimestamp            [128-167]", c.lastUpdateTimestamp, r.lastUpdateTimestamp);
        _check("  id                             [168-183]", uint16(w >> 168), r.id);
        _log(string.concat("  liquidationGracePeriodUntil    [184-223] = ", _u(uint40(w >> 184)), " (no legacy getter)"));
        _check("  unused bits must be zero       [224-255]", w >> 224, 0);
        _log(string.concat("  note: getReserveData().currentStableBorrowRate = ", _u(r.currentStableBorrowRate), " is hardcoded; bits 0-127 of this word now hold deficit"));
    }

    function _reserveWordsPackedAndAddresses(Ctx memory c) internal {
        IPool.ReserveDataLegacy memory r = c.pool.getReserveData(c.asset);

        uint256 w = _logWord(c, 4, "aTokenAddress [0-159]");
        _check("  aTokenAddress                  [0-159]", uint160(w), uint160(r.aTokenAddress));
        _check("  bits above the address are zero [160-255]", w >> 160, 0);

        w = _logWord(c, 5, "DEPRECATED v3.2 stableDebtTokenAddress (never read by getters)");
        _log(string.concat("  getReserveData().stableDebtTokenAddress = ", _a(r.stableDebtTokenAddress), " comes from provider.getAddress(\"MOCK_STABLE_DEBT\"), not this word"));

        w = _logWord(c, 6, "variableDebtTokenAddress [0-159]");
        _check("  variableDebtTokenAddress       [0-159]", uint160(w), uint160(r.variableDebtTokenAddress));

        w = _logWord(c, 7, "DEPRECATED v3.4 interestRateStrategyAddress (never read by getters)");
        _log(string.concat("  stored value equals the immutable strategy: ", address(uint160(w)) == r.interestRateStrategyAddress ? "yes" : "no"));

        w = _logWord(c, 8, "accruedToTreasury (scaled) [0-127] | virtualUnderlyingBalance [128-255]");
        c.accruedToTreasury = uint128(w);
        c.virtualUnderlyingBalance = uint128(w >> 128);
        _check("  accruedToTreasury (scaled)     [0-127]", c.accruedToTreasury, r.accruedToTreasury);
        _check("  virtualUnderlyingBalance       [128-255]", c.virtualUnderlyingBalance, c.pool.getVirtualUnderlyingBalance(c.asset));

        w = _logWord(c, 9, "DEPRECATED isolationModeTotalDebt [0-127] | DEPRECATED v3.4 virtualUnderlyingBalance [128-255]");
        _log(string.concat("  getReserveData(): unbacked = ", _u(r.unbacked), ", isolationModeTotalDebt = ", _u(r.isolationModeTotalDebt), " (both hardcoded)"));
    }

    // ------------------------------------------------------------------------------------------
    // 5. Configuration bitmap (base+0). Bit positions: ReserveConfiguration.sol @ v3.7.0
    // ------------------------------------------------------------------------------------------
    function _configurationParams(Ctx memory c) internal {
        _header("5. CONFIGURATION BITMAP (base+0), bit positions from ReserveConfiguration.sol@v3.7.0");
        uint256 w = _word(c, 0);
        (uint256 decimals, uint256 ltv, uint256 liqThreshold, uint256 liqBonus, uint256 reserveFactor,,,,,) =
            IPoolDataProvider(DATA_PROVIDER).getReserveConfigurationData(c.asset);
        c.decimals = (w >> 48) & 0xFF;
        _check("  ltv (bps)                      [0-15]", w & 0xFFFF, ltv);
        _check("  liquidationThreshold (bps)     [16-31]", (w >> 16) & 0xFFFF, liqThreshold);
        _check("  liquidationBonus (bps)         [32-47]", (w >> 32) & 0xFFFF, liqBonus);
        _check("  decimals                       [48-55]", c.decimals, decimals);
        _check("  reserveFactor (bps)            [64-79]", (w >> 64) & 0xFFFF, reserveFactor);
        _check(
            "  liquidationProtocolFee (bps)   [152-167]",
            (w >> 152) & 0xFFFF,
            IPoolDataProvider(DATA_PROVIDER).getLiquidationProtocolFee(c.asset)
        );
    }

    function _configurationFlagsAndCaps(Ctx memory c) internal {
        uint256 w = _word(c, 0);
        (,,,,,, bool borrowingEnabled,, bool isActive, bool isFrozen) =
            IPoolDataProvider(DATA_PROVIDER).getReserveConfigurationData(c.asset);
        (uint256 borrowCap, uint256 supplyCap) = IPoolDataProvider(DATA_PROVIDER).getReserveCaps(c.asset);
        _check("  isActive                       [56]", (w >> 56) & 1, isActive ? 1 : 0);
        _check("  isFrozen                       [57]", (w >> 57) & 1, isFrozen ? 1 : 0);
        _check("  borrowingEnabled               [58]", (w >> 58) & 1, borrowingEnabled ? 1 : 0);
        _check("  isPaused                       [60]", (w >> 60) & 1, IPoolDataProvider(DATA_PROVIDER).getPaused(c.asset) ? 1 : 0);
        _log(string.concat("  flashLoanEnabled               [63] = ", _u((w >> 63) & 1)));
        _check("  borrowCap (whole tokens)       [80-115]", (w >> 80) & 0xFFFFFFFFF, borrowCap);
        _check("  supplyCap (whole tokens)       [116-151]", (w >> 116) & 0xFFFFFFFFF, supplyCap);
        _log("  bits left by removed fields (printed, not asserted):");
        _log(string.concat("    [59] pre-3.2 stableBorrowRateEnabled = ", _u((w >> 59) & 1), " | [61] borrowableInIsolation = ", _u((w >> 61) & 1), " | [62] siloedBorrowing = ", _u((w >> 62) & 1)));
        _log(string.concat("    [168-251] eMode/unbackedMintCap/debtCeiling = ", _u((w >> 168) & ((uint256(1) << 84) - 1)), " | [252] virtualAccActive (deprecated v3.4) = ", _u((w >> 252) & 1), " | [253-255] = ", _u(w >> 253)));
    }

    // ------------------------------------------------------------------------------------------
    // 6. Total supply: computed at read time from raw slots + block.timestamp
    // ------------------------------------------------------------------------------------------
    function _supply(Ctx memory c) internal {
        _header("6. TOTAL SUPPLY = aToken._totalSupply (scaled) x normalizedIncome(now)");
        uint256 scaled = uint256(vm.load(c.aToken, bytes32(ATOKEN_TOTAL_SUPPLY_SLOT)));
        _check("aToken slot 54 _totalSupply == scaledTotalSupply()", scaled, IScaledBalanceToken(c.aToken).scaledTotalSupply());

        vm.record();
        c.totalSupply = IScaledBalanceToken(c.aToken).totalSupply();
        (bytes32[] memory tokenOps,) = vm.accesses(c.aToken);
        (bytes32[] memory poolOps,) = vm.accesses(address(c.pool));
        vm.stopRecord();
        _logReadSet("aToken.totalSupply() read set", c, c.aToken, tokenOps, poolOps, true);

        uint256 dt = block.timestamp - c.lastUpdateTimestamp;
        uint256 linear = RAY + (uint256(c.liquidityRate) * dt) / SECONDS_PER_YEAR; // MathUtils.calculateLinearInterest
        uint256 normIncome = dt == 0 ? c.liquidityIndex : _rayMul(linear, c.liquidityIndex); // ReserveLogic.getNormalizedIncome
        uint256 rebuilt = (scaled * normIncome) / RAY; // TokenMath.getATokenBalance = rayMulFloor
        _log(string.concat("dt = block.timestamp - lastUpdateTimestamp = ", _u(dt), " s"));
        _log(string.concat("linear = RAY + rate*dt/365d = ", _u(linear)));
        _check("normalizedIncome rebuilt == getReserveNormalizedIncome()", normIncome, c.pool.getReserveNormalizedIncome(c.asset));
        _check("totalSupply rebuilt (rayMulFloor) == aToken.totalSupply()", rebuilt, c.totalSupply);
        _log(string.concat("TOTAL SUPPLY = ", _fixed(c.totalSupply, c.decimals, c.decimals), "   (scaled: ", _fixed(scaled, c.decimals, c.decimals), ")"));
        _log(string.concat("accrued by reads alone since lastUpdateTimestamp = ", _fixed(rebuilt - (scaled * c.liquidityIndex) / RAY, c.decimals, c.decimals)));
    }

    // ------------------------------------------------------------------------------------------
    // 7. Total variable debt: same idea, compounded interest, rounded up
    // ------------------------------------------------------------------------------------------
    function _debt(Ctx memory c) internal {
        _header("7. TOTAL VARIABLE DEBT = vToken._totalSupply (scaled) x normalizedDebt(now)");
        uint256 scaled = uint256(vm.load(c.vToken, bytes32(VTOKEN_TOTAL_SUPPLY_SLOT)));
        _check("vToken slot 58 _totalSupply == scaledTotalSupply()", scaled, IScaledBalanceToken(c.vToken).scaledTotalSupply());

        vm.record();
        c.totalDebt = IScaledBalanceToken(c.vToken).totalSupply();
        (bytes32[] memory tokenOps,) = vm.accesses(c.vToken);
        (bytes32[] memory poolOps,) = vm.accesses(address(c.pool));
        vm.stopRecord();
        _logReadSet("vToken.totalSupply() read set", c, c.vToken, tokenOps, poolOps, false);

        uint256 dt = block.timestamp - c.lastUpdateTimestamp;
        uint256 x = (uint256(c.variableBorrowRate) * dt) / SECONDS_PER_YEAR; // MathUtils.calculateCompoundedInterest
        uint256 compounded = RAY + x + _rayMul(x, x / 2 + _rayMul(x, x / 6));
        uint256 normDebt = dt == 0 ? c.variableBorrowIndex : _rayMul(compounded, c.variableBorrowIndex); // ReserveLogic.getNormalizedDebt
        uint256 rebuilt = _rayMulCeil(scaled, normDebt); // TokenMath.getVTokenBalance = rayMulCeil
        _log(string.concat("x = rate*dt/365d = ", _u(x), "; compounded = RAY + x + x*(x/2 + x*x/6) = ", _u(compounded)));
        _check("normalizedDebt rebuilt == getReserveNormalizedVariableDebt()", normDebt, c.pool.getReserveNormalizedVariableDebt(c.asset));
        _check("totalDebt rebuilt (rayMulCeil) == vToken.totalSupply()", rebuilt, c.totalDebt);
        _log(string.concat("TOTAL VARIABLE DEBT = ", _fixed(c.totalDebt, c.decimals, c.decimals), "   (scaled: ", _fixed(scaled, c.decimals, c.decimals), ")"));
        _log(string.concat("accrued by reads alone since lastUpdateTimestamp = ", _fixed(rebuilt - _rayMulCeil(scaled, c.variableBorrowIndex), c.decimals, c.decimals)));
    }

    // ------------------------------------------------------------------------------------------
    // 8. Rates and adjacent raw components (printed side by side; no relationship asserted)
    // ------------------------------------------------------------------------------------------
    function _ratesAndComponents(Ctx memory c) internal view {
        _header("8. RATES (annual, in ray) and adjacent components");
        _log(string.concat("supply currentLiquidityRate      = ", _fixed(uint256(c.liquidityRate) * 100, 27, 4), " % APR"));
        _log(string.concat("borrow currentVariableBorrowRate = ", _fixed(uint256(c.variableBorrowRate) * 100, 27, 4), " % APR"));
        _log(string.concat("both last written at ", _u(c.lastUpdateTimestamp), ", ", _u(block.timestamp - c.lastUpdateTimestamp), " s before this block; they change only on state-changing actions"));
        _log("components (underlying units unless noted):");
        _log(string.concat("  aToken.totalSupply()           = ", _fixed(c.totalSupply, c.decimals, c.decimals)));
        _log(string.concat("  vToken.totalSupply()           = ", _fixed(c.totalDebt, c.decimals, c.decimals)));
        _log(string.concat("  virtualUnderlyingBalance       = ", _fixed(c.virtualUnderlyingBalance, c.decimals, c.decimals)));
        _log(string.concat("  accruedToTreasury (SCALED)     = ", _fixed(c.accruedToTreasury, c.decimals, c.decimals), "  (not in aToken totalSupply until mintToTreasury)"));
        _log(string.concat("  deficit                        = ", _fixed(c.deficit, c.decimals, c.decimals)));
    }

    // ------------------------------------------------------------------------------------------
    // Helpers
    // ------------------------------------------------------------------------------------------
    function _word(Ctx memory c, uint256 k) internal view returns (uint256) {
        return uint256(vm.load(address(c.pool), bytes32(uint256(c.base) + k)));
    }

    function _logWord(Ctx memory c, uint256 k, string memory fields) internal view returns (uint256 w) {
        w = _word(c, k);
        _log(string.concat("base+", _u(k), "  slot ", _b32(bytes32(uint256(c.base) + k)), "  ", fields));
        _log(string.concat("        raw  ", _b32(bytes32(w))));
    }

    function _logReadSet(
        string memory title,
        Ctx memory c,
        address token,
        bytes32[] memory tokenOps,
        bytes32[] memory poolOps,
        bool isAToken
    ) internal pure {
        bytes32[] memory tokenSlots = _unique(tokenOps);
        bytes32[] memory poolSlots = _unique(poolOps);
        _log(string.concat(title, ": token ", _u(tokenSlots.length), " slots, pool ", _u(poolSlots.length), " slots, plus block.timestamp"));
        for (uint256 i = 0; i < tokenSlots.length; i++) {
            _log(string.concat("  token ", _a(token), " ", _b32(tokenSlots[i]), " <- ", _tokenSlotLabel(tokenSlots[i], isAToken)));
        }
        for (uint256 i = 0; i < poolSlots.length; i++) {
            _log(string.concat("  pool  ", _a(address(c.pool)), " ", _b32(poolSlots[i]), " <- ", _poolSlotLabel(c.base, poolSlots[i])));
        }
    }

    function _poolSlotLabel(bytes32 base, bytes32 slot) internal pure returns (string memory) {
        if (slot == EIP1967_IMPL_SLOT) return "EIP-1967 implementation slot (proxy routing)";
        if (uint256(slot) >= uint256(base) && uint256(slot) - uint256(base) < 10) {
            return string.concat("_reserves[asset] base+", _u(uint256(slot) - uint256(base)));
        }
        return "unlabelled";
    }

    function _tokenSlotLabel(bytes32 slot, bool isAToken) internal pure returns (string memory) {
        if (slot == EIP1967_IMPL_SLOT) return "EIP-1967 implementation slot (proxy routing)";
        uint256 s = uint256(slot);
        if (s == (isAToken ? ATOKEN_TOTAL_SUPPLY_SLOT : VTOKEN_TOTAL_SUPPLY_SLOT)) return "_totalSupply (scaled)";
        if (s == (isAToken ? ATOKEN_UNDERLYING_SLOT : VTOKEN_UNDERLYING_SLOT)) return "_underlyingAsset";
        return "unlabelled";
    }

    function _check(string memory label, uint256 raw, uint256 getter) internal {
        bool ok = raw == getter;
        if (ok) passed++;
        else mismatched++;
        _log(string.concat(label, "  raw=", _u(raw), "  getter=", _u(getter), "  ", ok ? "OK" : "MISMATCH"));
    }

    function _release(uint256 revision) internal pure returns (string memory) {
        if (revision == 7) return "v3.3.0";
        if (revision == 8) return "v3.4.0";
        if (revision == 9) return "v3.5.0";
        if (revision == 10) return "v3.6.0";
        if (revision == 11) return "v3.7.0";
        return "unknown revision (check aave-v3-origin tags)";
    }

    function _rayMul(uint256 a, uint256 b) internal pure returns (uint256) {
        return (a * b + HALF_RAY) / RAY; // WadRayMath.rayMul: round half up
    }

    function _rayMulCeil(uint256 a, uint256 b) internal pure returns (uint256) {
        uint256 product = a * b;
        return product / RAY + (product % RAY == 0 ? 0 : 1); // WadRayMath.rayMulCeil
    }

    function _contains(bytes32[] memory values, bytes32 needle) internal pure returns (bool) {
        for (uint256 i = 0; i < values.length; i++) {
            if (values[i] == needle) return true;
        }
        return false;
    }

    /// @dev Order-preserving de-duplication (vm.accesses lists every SLOAD op, including repeats).
    function _unique(bytes32[] memory values) internal pure returns (bytes32[] memory out) {
        out = new bytes32[](values.length);
        uint256 n;
        for (uint256 i = 0; i < values.length; i++) {
            bool seen;
            for (uint256 j = 0; j < n; j++) {
                if (out[j] == values[i]) {
                    seen = true;
                    break;
                }
            }
            if (!seen) out[n++] = values[i];
        }
        assembly {
            mstore(out, n)
        }
    }

    /// @dev Fixed-point decimal rendering: value / 10**decimals with `shown` fractional digits (truncated).
    function _fixed(uint256 value, uint256 decimals, uint256 shown) internal pure returns (string memory) {
        uint256 unit = 10 ** decimals;
        string memory integerPart = _u(value / unit);
        if (shown == 0) return integerPart;
        if (shown > decimals) shown = decimals;
        bytes memory digits = bytes(_u((value % unit) / 10 ** (decimals - shown)));
        bytes memory padded = new bytes(shown);
        uint256 pad = shown - digits.length;
        for (uint256 i = 0; i < shown; i++) {
            padded[i] = i < pad ? bytes1("0") : digits[i - pad];
        }
        return string.concat(integerPart, ".", string(padded));
    }

    function _header(string memory title) internal pure {
        _log("");
        _log(string.concat("=== ", title, " ==="));
    }

    function _log(string memory line) internal pure {
        console2.log(line);
    }

    function _u(uint256 v) internal pure returns (string memory) {
        return vm.toString(v);
    }

    function _a(address v) internal pure returns (string memory) {
        return vm.toString(v);
    }

    function _b32(bytes32 v) internal pure returns (string memory) {
        return vm.toString(v);
    }
}
