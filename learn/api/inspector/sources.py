"""Addresses and citations. Every hardcoded value here has a public source, and the stages re-verify each
one on-chain (registry lookups, code presence, getter cross-checks)."""

from __future__ import annotations

ADDRESS_BOOK_REPO = "aave-dao/aave-address-book"
# Address book commit on main (2026-09-13): a public git commit SHA, not a secret.
ADDRESS_BOOK_COMMIT = "02748a20592a019e834aee193b6c40c9bc7bd059"  # pragma: allowlist secret
ADDRESS_BOOK_FILE = "src/AaveV3Arbitrum.sol"


def address_book(lines: str) -> str:
    return f"https://github.com/{ADDRESS_BOOK_REPO}/blob/{ADDRESS_BOOK_COMMIT}/{ADDRESS_BOOK_FILE}#{lines}"


AAVE_TAG = "v3.7.0"


def aave_source(path: str, lines: str) -> str:
    return f"https://github.com/aave-dao/aave-v3-origin/blob/{AAVE_TAG}/{path}#{lines}"


CIRCLE_PROXY_SOURCE = (
    "https://github.com/circlefin/stablecoin-evm/blob/fc85788bc7c23cefe3df1a757133048bfddadeaa/"
    "contracts/upgradeability/UpgradeabilityProxy.sol#L42-L55"
)

# Arbitrum One, verified against the sources above.
POOL_ADDRESSES_PROVIDER = "0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb"  # address book L8-L9
POOL = "0x794a61358D6845594F94dc1DB02A252b5b4814aD"  # address book L12
USDC = "0xaf88d065e77c8cC2239327C5EDb3A432268e5831"  # address book L407 (USDCn), Circle docs
USDC_E = "0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8"  # address book L177 (legacy name "USDC")
USDC_A_TOKEN = "0x724dc807b04555b71ed48a6896b6F41593b8C637"  # address book L412
USDC_V_TOKEN = "0xf611aEb5013fD2c0511c9CD55c7dc5C1140741A6"  # address book L415

REVISION_TO_TAG = {7: "v3.3.0", 8: "v3.4.0", 9: "v3.5.0", 10: "v3.6.0", 11: "v3.7.0"}

CITATIONS = [
    {"id": "aave-docs", "label": "Aave docs: addresses come from the Aave Address Book", "url": "https://aave.com/docs/resources/addresses"},
    {"id": "book-provider", "label": "Address book: POOL_ADDRESSES_PROVIDER", "url": address_book("L8-L9")},
    {"id": "book-pool", "label": "Address book: POOL", "url": address_book("L12")},
    {"id": "book-usdcn", "label": "Address book: USDCn_UNDERLYING (native USDC)", "url": address_book("L407")},
    {"id": "book-usdcn-atoken", "label": "Address book: USDCn_A_TOKEN", "url": address_book("L412")},
    {"id": "book-usdcn-vtoken", "label": "Address book: USDCn_V_TOKEN", "url": address_book("L415")},
    {"id": "book-usdce", "label": "Address book: USDC_UNDERLYING (bridged USDC.e)", "url": address_book("L177")},
    {"id": "circle-docs", "label": "Circle: native USDC contract addresses", "url": "https://developers.circle.com/stablecoins/usdc-contract-addresses"},
    {"id": "arbitrum-docs", "label": "Arbitrum docs: native USDC vs bridged USDC.e", "url": "https://docs.arbitrum.io/arbitrum-bridge/usdc-arbitrum-one"},
    {"id": "eip1967", "label": "Aave proxy: EIP-1967 implementation slot", "url": aave_source("src/contracts/dependencies/openzeppelin/upgradeability/BaseUpgradeabilityProxy.sol", "L22-L25")},
    {"id": "circle-proxy", "label": "Circle proxy: ZeppelinOS implementation slot", "url": CIRCLE_PROXY_SOURCE},
    {"id": "pool-inheritance", "label": "Pool is VersionedInitializable, PoolStorage, ...", "url": aave_source("src/contracts/protocol/pool/Pool.sol", "L38")},
    {"id": "versioned-initializable", "label": "VersionedInitializable storage (slots 0, 1, gap 2-51)", "url": aave_source("src/contracts/misc/aave-upgradeability/VersionedInitializable.sol", "L29")},
    {"id": "pool-storage", "label": "PoolStorage._reserves (slot 52)", "url": aave_source("src/contracts/protocol/pool/PoolStorage.sol", "L21")},
    {"id": "reserve-data", "label": "DataTypes.ReserveData (storage layout)", "url": aave_source("src/contracts/protocol/libraries/types/DataTypes.sol", "L42")},
    {"id": "reserve-data-legacy", "label": "DataTypes.ReserveDataLegacy (getReserveData ABI)", "url": aave_source("src/contracts/protocol/libraries/types/DataTypes.sol", "L9")},
    {"id": "get-reserve-data", "label": "Pool.getReserveData body", "url": aave_source("src/contracts/protocol/pool/Pool.sol", "L438")},
    {"id": "reserve-configuration", "label": "ReserveConfiguration bit positions", "url": aave_source("src/contracts/protocol/libraries/configuration/ReserveConfiguration.sol", "L13-L53")},
]
