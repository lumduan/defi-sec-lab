"""Decode Aave's ReserveConfigurationMap (one uint256) into fields.

Bit positions: aave-v3-origin v3.7.0, src/contracts/protocol/libraries/configuration/ReserveConfiguration.sol
lines 13-53. Multi-bit fields span whole 4-bit groups, so each one reads straight off hex characters.
"""

from __future__ import annotations

from . import evm

SOURCE = (
    "https://github.com/aave-dao/aave-v3-origin/blob/v3.7.0/"
    "src/contracts/protocol/libraries/configuration/ReserveConfiguration.sol#L13-L53"
)

# (name, lo, hi, unit, is_risk_param)
FIELDS = [
    ("ltv", 0, 15, "bps", True),
    ("liquidationThreshold", 16, 31, "bps", True),
    ("liquidationBonus", 32, 47, "bps", True),
    ("decimals", 48, 55, "decimals", False),
    ("reserveFactor", 64, 79, "bps", False),
    ("borrowCap", 80, 115, "whole tokens", False),
    ("supplyCap", 116, 151, "whole tokens", False),
    ("liquidationProtocolFee", 152, 167, "bps", False),
]
FLAGS = [
    (56, "active"),
    (57, "frozen"),
    (58, "borrowingEnabled"),
    (59, "unused (pre-3.2 stableBorrowRateEnabled)"),
    (60, "paused"),
    (61, "unused (pre-3.7 borrowableInIsolation)"),
    (62, "unused (pre-3.7 siloedBorrowing)"),
    (63, "flashLoanEnabled"),
]
HOLES = [
    (168, 175, "pre-3.2 eModeCategory"),
    (176, 211, "pre-3.4 unbackedMintCap"),
    (212, 251, "pre-3.7 debtCeiling"),
    (252, 252, "virtualAccActive (deprecated in v3.4)"),
    (253, 255, "unused"),
]


def _hex_slice(word: str, lo: int, hi: int) -> str:
    return word[64 - (hi + 1) // 4 : 64 - lo // 4]


def _human(unit: str, raw: int) -> str:
    if unit == "bps":
        return f"{raw / 100:.2f} %"
    if unit == "whole tokens":
        return f"{raw:,}"
    return str(raw)


def decode_configuration(word: str) -> dict:
    w = evm.normalize_word(word)
    value = int(w, 16)
    fields = []
    for name, lo, hi, unit, risk in FIELDS:
        raw = evm.bits(value, lo, hi)
        fields.append(
            {
                "name": name,
                "bits": f"{lo}-{hi}",
                "hex": _hex_slice(w, lo, hi),
                "raw": raw,
                "unit": unit,
                "human": _human(unit, raw),
                "risk_param": risk,
            }
        )
    flags_byte = evm.bits(value, 56, 63)
    flags = [{"bit": bit, "name": name, "value": (value >> bit) & 1} for bit, name in FLAGS]
    holes = [
        {"bits": f"{lo}-{hi}", "name": name, "raw": evm.bits(value, lo, hi)} for lo, hi, name in HOLES
    ]
    return {
        "word": "0x" + w,
        "raw": str(value),
        "source": SOURCE,
        "fields": fields,
        "flags_byte": {"bits": "56-63", "hex": _hex_slice(w, 56, 63), "binary": f"{flags_byte:08b}", "flags": flags},
        "holes": holes,
    }
