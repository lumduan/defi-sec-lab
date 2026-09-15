"""EVM helpers: keccak256, EIP-55 checksums, ABI words, storage slot math. Pure functions, no I/O."""

from __future__ import annotations

from Crypto.Hash import keccak as _keccak


def keccak256(data: bytes) -> bytes:
    h = _keccak.new(digest_bits=256)
    h.update(data)
    return h.digest()


def keccak_hex(data: bytes) -> str:
    return "0x" + keccak256(data).hex()


def strip0x(value: str) -> str:
    return value[2:] if value[:2] in ("0x", "0X") else value


def hex_to_int(value: str) -> int:
    return int(strip0x(value) or "0", 16)


def int_to_word(n: int) -> str:
    """A uint256 as 64 lowercase hex chars (no 0x)."""
    return f"{n:064x}"


def normalize_word(value: str) -> str:
    """A storage/ABI word as returned by any node, normalized to 64 lowercase hex chars."""
    return int_to_word(hex_to_int(value))


def words(data: str) -> list[str]:
    d = strip0x(data).lower()
    if len(d) % 64:
        raise ValueError(f"ABI data length {len(d)} hex chars is not a multiple of 64")
    return [d[i : i + 64] for i in range(0, len(d), 64)]


def byte_length(data: str) -> int:
    return len(strip0x(data)) // 2


def to_checksum(address: str) -> str:
    """EIP-55 mixed-case checksum address."""
    a = strip0x(address).lower()
    if len(a) != 40 or any(c not in "0123456789abcdef" for c in a):
        raise ValueError("not a 20-byte hex address")
    digest = keccak256(a.encode()).hex()
    return "0x" + "".join(c.upper() if c.isalpha() and int(digest[i], 16) >= 8 else c for i, c in enumerate(a))


def address_from_word(word: str) -> str:
    return to_checksum(normalize_word(word)[-40:])


def selector(signature: str) -> str:
    return keccak_hex(signature.encode())[:10]


def encode_address(address: str) -> str:
    return strip0x(address).lower().rjust(64, "0")


def mapping_slot(key_address: str, declared_slot: int) -> tuple[str, str]:
    """Solidity mapping(address => T) entry location: keccak256(abi.encode(key, declared_slot))."""
    preimage = encode_address(key_address) + int_to_word(declared_slot)
    return "0x" + preimage, keccak_hex(bytes.fromhex(preimage))


def bits(value: int, lo: int, hi: int) -> int:
    return (value >> lo) & ((1 << (hi - lo + 1)) - 1)


def push4_selector_present(code: str, sig: str) -> bool:
    """True if the bytecode contains PUSH4 (0x63) followed by the selector at a byte boundary."""
    needle = "63" + selector(sig)[2:]
    hexcode = strip0x(code).lower()
    i = hexcode.find(needle)
    while i != -1:
        if i % 2 == 0:
            return True
        i = hexcode.find(needle, i + 1)
    return False


# Proxy implementation slots.
#   EIP-1967:  keccak256("eip1967.proxy.implementation") - 1   (Aave; OpenZeppelin BaseUpgradeabilityProxy)
#   ZeppelinOS: keccak256("org.zeppelinos.proxy.implementation") (Circle FiatTokenProxy / UpgradeabilityProxy)
EIP1967_IMPLEMENTATION_SLOT = "0x" + int_to_word(hex_to_int(keccak_hex(b"eip1967.proxy.implementation")) - 1)
ZEPPELINOS_IMPLEMENTATION_SLOT = keccak_hex(b"org.zeppelinos.proxy.implementation")
