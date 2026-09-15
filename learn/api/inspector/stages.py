"""The four stages of notes/00, rebuilt from raw RPC results. Raw values are always kept next to the decoded ones.

Stage 1 "Are we in the real bank?"   chain id, block, hash checks, client version
Stage 2 "Storefront vs backroom"     proxy vs implementation (code sizes, implementation slots, USDC's edge case)
Stage 3 "Open the books"             getReserveData(USDC): 480 raw bytes -> 15 words -> units
Stage 4 "Read through to raw memory" liquidityIndex via function vs raw proxy storage (two uint128 in one slot)
"""

from __future__ import annotations

from typing import Any

from . import bitmap, evm, fmt
from . import sources as src
from .rpc import RpcClient, RpcError

ARBITRUM_ONE = 42161


def _check(check_id: str, label: str, expected: Any, actual: Any, passed: bool | None, status: str | None = None,
           note: str | None = None) -> dict:
    return {
        "id": check_id,
        "label": label,
        "expected": expected,
        "actual": actual,
        "pass": passed,
        "status": status or ("pass" if passed else "fail"),
        "note": note,
    }


# ---------------------------------------------------------------------------------------------------------------
# Stage 1
# ---------------------------------------------------------------------------------------------------------------
def stage1(client: RpcClient, tag: str, source: str, pin_number: int | None, pin_hash: str | None,
           upstream: RpcClient | None) -> dict:
    chain_raw = client.call("eth_chainId", [])
    head_raw = client.call("eth_blockNumber", [])
    version = client.call("web3_clientVersion", [])
    block = client.call("eth_getBlockByNumber", [tag, False])
    selected = {k: block.get(k) for k in ("number", "hash", "parentHash", "timestamp", "l1BlockNumber")}

    chain_id = evm.hex_to_int(chain_raw)
    head = evm.hex_to_int(head_raw)
    number = evm.hex_to_int(block["number"])
    timestamp = evm.hex_to_int(block["timestamp"])
    l1 = evm.hex_to_int(block["l1BlockNumber"]) if block.get("l1BlockNumber") else None

    checks = [_check("chain_id", "Chain id is Arbitrum One", str(ARBITRUM_ONE), str(chain_id), chain_id == ARBITRUM_ONE)]
    if source == "fork":
        checks.append(_check("head_is_pin", "Fork head is the committed pin (fork.env FORK_BLOCK_NUMBER)",
                             str(pin_number), str(head), pin_number is not None and head == pin_number))
        checks.append(_check("hash_is_pin", "Block hash equals the committed hash (fork.env FORK_BLOCK_HASH)",
                             pin_hash, block["hash"], bool(pin_hash) and block["hash"].lower() == pin_hash))
        if upstream is None:
            checks.append(_check("hash_is_real_chain", "Real Arbitrum chain has the same hash at this height",
                                 None, block["hash"], None, "not_configured", "RPC_URL is not configured"))
        else:
            try:
                real = upstream.call("eth_getBlockByNumber", [tag, False])
                checks.append(_check("hash_is_real_chain", "Real Arbitrum chain has the same hash at this height (via RPC_URL)",
                                     real["hash"], block["hash"], real["hash"].lower() == block["hash"].lower()))
            except RpcError as exc:
                checks.append(_check("hash_is_real_chain", "Real Arbitrum chain has the same hash at this height",
                                     None, block["hash"], None, "unavailable", str(exc)))
    else:
        checks.append(_check("live_head", "Reading the real chain's latest block (no fork, no pin)",
                             "latest", str(number), True, "info"))

    return {
        "id": "chain",
        "title": "Are we in the real bank?",
        "client": source,
        "client_version": version,
        "block": {
            "number": number,
            "number_hex": block["number"],
            "hash": block["hash"],
            "timestamp": timestamp,
            "timestamp_hex": block["timestamp"],
            "timestamp_iso": fmt.iso_utc(timestamp),
            "l1_block_number": l1,
            "l1_block_number_hex": block.get("l1BlockNumber"),
        },
        "exchanges": [
            {"method": "eth_chainId", "params": [], "result": chain_raw, "decoded": str(chain_id)},
            {"method": "eth_blockNumber", "params": [], "result": head_raw, "decoded": str(head)},
            {"method": "web3_clientVersion", "params": [], "result": version, "decoded": version},
            {"method": "eth_getBlockByNumber", "params": [tag, False], "result": selected,
             "decoded": f"block {number}, timestamp {fmt.iso_utc(timestamp)}", "note": "selected fields"},
        ],
        "checks": checks,
    }


# ---------------------------------------------------------------------------------------------------------------
# Stage 2
# ---------------------------------------------------------------------------------------------------------------
PROXY_SIGNATURES = ["implementation()", "upgradeTo(address)", "upgradeToAndCall(address,bytes)", "admin()", "changeAdmin(address)"]
CONTRACTS = [
    ("pool", "Aave V3 Pool", src.POOL, "book-pool"),
    ("atoken", "aToken (aArbUSDCn)", src.USDC_A_TOKEN, "book-usdcn-atoken"),
    ("vtoken", "Variable debt token (variableDebtArbUSDCn)", src.USDC_V_TOKEN, "book-usdcn-vtoken"),
    ("usdc", "USDC (native, Circle)", src.USDC, "book-usdcn"),
    ("usdce", "USDC.e (bridged)", src.USDC_E, "book-usdce"),
]


def _slot_derivation(preimage: str, minus_one: bool) -> dict:
    digest = evm.keccak_hex(preimage.encode())
    slot = "0x" + evm.int_to_word(evm.hex_to_int(digest) - 1) if minus_one else digest
    return {"preimage": preimage, "keccak256": digest, "minus_one": minus_one, "slot": slot}


def stage2(client: RpcClient, tag: str) -> dict:
    get_pool = evm.selector("getPool()")
    registry_raw = client.call("eth_call", [{"to": src.POOL_ADDRESSES_PROVIDER, "data": get_pool}, tag])
    registry_pool = evm.address_from_word(registry_raw)

    rows = []
    for key, label, address, citation in CONTRACTS:
        code = client.call("eth_getCode", [address, tag])
        eip = evm.normalize_word(client.call("eth_getStorageAt", [address, evm.EIP1967_IMPLEMENTATION_SLOT, tag]))
        zos = evm.normalize_word(client.call("eth_getStorageAt", [address, evm.ZEPPELINOS_IMPLEMENTATION_SLOT, tag]))
        found = "eip1967" if int(eip, 16) else ("zeppelinos" if int(zos, 16) else None)
        implementation = None
        if found:
            impl_address = evm.address_from_word(eip if found == "eip1967" else zos)
            implementation = {"address": impl_address, "code_size": evm.byte_length(client.call("eth_getCode", [impl_address, tag]))}
        rows.append({
            "key": key,
            "label": label,
            "address": address,
            "citation": citation,
            "proxy": {
                "code_size": evm.byte_length(code),
                "code_head": "0x" + evm.strip0x(code)[:64],
                "dispatcher_selectors": [
                    {"signature": sig, "selector": evm.selector(sig), "push4_found": evm.push4_selector_present(code, sig)}
                    for sig in PROXY_SIGNATURES
                ],
            },
            "slots": {"eip1967": "0x" + eip, "zeppelinos": "0x" + zos},
            "implementation_slot": found,
            "implementation": implementation,
            "edge": found == "zeppelinos",
        })

    return {
        "id": "proxies",
        "title": "Storefront vs backroom",
        "slot_derivations": {
            "eip1967": {**_slot_derivation("eip1967.proxy.implementation", True), "citation": "eip1967"},
            "zeppelinos": {**_slot_derivation("org.zeppelinos.proxy.implementation", False), "citation": "circle-proxy"},
        },
        "registry": {
            "call": "PoolAddressesProvider.getPool()",
            "to": src.POOL_ADDRESSES_PROVIDER,
            "selector": get_pool,
            "result": registry_raw,
            "decoded": registry_pool,
            "address_book": src.POOL,
            "match": registry_pool.lower() == src.POOL.lower(),
        },
        "rows": rows,
        "edge_note": (
            "Native USDC keeps its implementation pointer in the ZeppelinOS slot, not the EIP-1967 slot. "
            "Tools that only read EIP-1967 (for example `cast implementation`) report no implementation at all."
        ),
    }


# ---------------------------------------------------------------------------------------------------------------
# Stage 3
# ---------------------------------------------------------------------------------------------------------------
LEGACY_FIELDS = [
    ("configuration", "uint256"),
    ("liquidityIndex", "uint128"),
    ("currentLiquidityRate", "uint128"),
    ("variableBorrowIndex", "uint128"),
    ("currentVariableBorrowRate", "uint128"),
    ("currentStableBorrowRate", "uint128"),
    ("lastUpdateTimestamp", "uint40"),
    ("id", "uint16"),
    ("aTokenAddress", "address"),
    ("stableDebtTokenAddress", "address"),
    ("variableDebtTokenAddress", "address"),
    ("interestRateStrategyAddress", "address"),
    ("accruedToTreasury", "uint128"),
    ("unbacked", "uint128"),
    ("isolationModeTotalDebt", "uint128"),
]
FIELD_NOTES = {
    "configuration": "bitmap of risk parameters and flags (decoded below)",
    "currentStableBorrowRate": "deprecated since v3.2: the getter returns 0 (storage now holds `deficit` here)",
    "stableDebtTokenAddress": "not reserve storage: provider.getAddress(\"MOCK_STABLE_DEBT\")",
    "interestRateStrategyAddress": "not storage: an immutable compiled into the Pool implementation",
    "accruedToTreasury": "scaled units, not USDC",
    "unbacked": "deprecated since v3.4: the getter returns 0",
    "isolationModeTotalDebt": "deprecated since v3.7: the getter returns 0",
}


def stage3(client: RpcClient, tag: str, block_timestamp: int) -> dict:
    fn_selector = evm.selector("getReserveData(address)")
    calldata = fn_selector + evm.encode_address(src.USDC)
    returndata = client.call("eth_call", [{"to": src.POOL, "data": calldata}, tag])
    ws = evm.words(returndata)
    if len(ws) != len(LEGACY_FIELDS):
        raise RpcError(f"getReserveData returned {len(ws)} words, expected {len(LEGACY_FIELDS)}")

    fields, by_name = [], {}
    for i, (name, typ) in enumerate(LEGACY_FIELDS):
        raw = int(ws[i], 16)
        entry: dict[str, Any] = {"index": i, "name": name, "type": typ, "word": "0x" + ws[i], "raw": str(raw),
                                 "note": FIELD_NOTES.get(name)}
        if typ == "address":
            entry["decoded"] = evm.address_from_word(ws[i])
        elif name in ("currentLiquidityRate", "currentVariableBorrowRate"):
            entry["decoded"] = fmt.ray_rate(raw)
        elif name in ("liquidityIndex", "variableBorrowIndex"):
            entry["decoded"] = fmt.ray_index(raw)
        elif name == "lastUpdateTimestamp":
            entry["decoded"] = {"iso": fmt.iso_utc(raw), "seconds_before_block": block_timestamp - raw}
        else:
            entry["decoded"] = str(raw)
        fields.append(entry)
        by_name[name] = entry

    configuration = bitmap.decode_configuration(ws[0])
    return {
        "id": "books",
        "title": "Open the books",
        "call": {
            "to": src.POOL,
            "function": "getReserveData(address)",
            "argument": src.USDC,
            "selector": fn_selector,
            "calldata": calldata,
            "block_tag": tag,
            "returndata": returndata,
            "returndata_bytes": evm.byte_length(returndata),
            "word_count": len(ws),
        },
        "fields": fields,
        "rates": {
            "supply": {"field": "currentLiquidityRate", **by_name["currentLiquidityRate"]["decoded"]},
            "borrow": {"field": "currentVariableBorrowRate", **by_name["currentVariableBorrowRate"]["decoded"]},
        },
        "risk_params": [f for f in configuration["fields"] if f["risk_param"]],
        "configuration": configuration,
        "last_update": {"raw": by_name["lastUpdateTimestamp"]["raw"], **by_name["lastUpdateTimestamp"]["decoded"],
                        "block_timestamp": block_timestamp},
    }


# ---------------------------------------------------------------------------------------------------------------
# Stage 4
# ---------------------------------------------------------------------------------------------------------------
RESERVES_DECLARED_SLOT = 52


def stage4(client: RpcClient, tag: str, proxies: dict, books: dict, allow_trace: bool) -> dict:
    pool_row = next(r for r in proxies["rows"] if r["key"] == "pool")
    implementation = pool_row["implementation"]["address"]

    slot0 = evm.normalize_word(client.call("eth_getStorageAt", [src.POOL, "0x0", tag]))
    revision_code = evm.hex_to_int(client.call("eth_call", [{"to": src.POOL, "data": evm.selector("POOL_REVISION()")}, tag]))

    preimage, base = evm.mapping_slot(src.USDC, RESERVES_DECLARED_SLOT)
    slot = "0x" + evm.int_to_word(evm.hex_to_int(base) + 1)
    word = evm.normalize_word(client.call("eth_getStorageAt", [src.POOL, slot, tag]))
    high_hex, low_hex = word[:32], word[32:]
    high, low = int(high_hex, 16), int(low_hex, 16)

    fn = {f["name"]: f for f in books["fields"]}
    comparisons = [
        {"field": "liquidityIndex", "bits": "0-127 (low half)", "hex": "0x" + low_hex, "storage": str(low),
         "function": fn["liquidityIndex"]["raw"], "match": str(low) == fn["liquidityIndex"]["raw"]},
        {"field": "currentLiquidityRate", "bits": "128-255 (high half)", "hex": "0x" + high_hex, "storage": str(high),
         "function": fn["currentLiquidityRate"]["raw"], "match": str(high) == fn["currentLiquidityRate"]["raw"]},
    ]

    impl_word = evm.normalize_word(client.call("eth_getStorageAt", [implementation, slot, tag]))
    trace: dict[str, Any] = {"available": False, "note": "node trace is only requested from the local fork"}
    if allow_trace:
        prestate = client.call("debug_traceCall", [{"to": src.POOL, "data": books["call"]["calldata"]}, tag, {"tracer": "prestateTracer"}])
        storage = (prestate.get(src.POOL.lower()) or {}).get("storage") or {}
        read = {evm.normalize_word(k): evm.normalize_word(v) for k, v in storage.items()}
        slot_word = evm.strip0x(slot)
        trace = {
            "available": True,
            "tracer": "prestateTracer",
            "pool_slots_read": len(read),
            "read_slot": slot_word in read,
            "value_at_read": ("0x" + read[slot_word]) if slot_word in read else None,
            "value_matches": read.get(slot_word) == word,
        }

    return {
        "id": "memory",
        "title": "Read through to raw memory",
        "proxy": {
            "address": src.POOL,
            "implementation": implementation,
            "slot0_word": "0x" + slot0,
            "revision_in_storage": int(slot0, 16),
            "revision_in_code": revision_code,
            "source_tag": src.REVISION_TO_TAG.get(revision_code, "unknown"),
        },
        "layout": [
            {"slot": "0", "name": "lastInitializedRevision", "type": "uint256", "contract": "VersionedInitializable", "citation": "versioned-initializable"},
            {"slot": "1", "name": "initializing", "type": "bool", "contract": "VersionedInitializable", "citation": "versioned-initializable"},
            {"slot": "2-51", "name": "______gap", "type": "uint256[50]", "contract": "VersionedInitializable", "citation": "versioned-initializable"},
            {"slot": "52", "name": "_reserves", "type": "mapping(address => ReserveData)", "contract": "PoolStorage", "citation": "pool-storage"},
        ],
        "mapping": {
            "key": src.USDC,
            "declared_slot": RESERVES_DECLARED_SLOT,
            "preimage": preimage,
            "base": base,
            "field_offset": 1,
            "slot": slot,
            "struct_order": ["base+0 configuration (uint256)", "base+1 liquidityIndex (uint128) | currentLiquidityRate (uint128)"],
        },
        "storage": {"method": "eth_getStorageAt", "address": src.POOL, "slot": slot, "block_tag": tag, "word": "0x" + word,
                    "high_hex": "0x" + high_hex, "low_hex": "0x" + low_hex, "high": str(high), "low": str(low)},
        "comparisons": comparisons,
        "controls": {
            "implementation_storage": {"address": implementation, "slot": slot, "word": "0x" + impl_word, "is_zero": int(impl_word, 16) == 0},
            "trace": trace,
        },
    }
