"""Known-answer tests for the EVM helpers (values cross-checked with cast in notes/00)."""

from inspector import evm


def test_keccak_known_answer():
    assert evm.keccak_hex(b"") == "0xc5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470"


def test_proxy_implementation_slots():
    assert evm.EIP1967_IMPLEMENTATION_SLOT == "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
    assert evm.ZEPPELINOS_IMPLEMENTATION_SLOT == "0x7050c9e0f4ca769c69bd3a8ef740bc37934f8e2c036e5a723fd8ee048ed3f8c3"


def test_usdc_reserve_mapping_slot():
    preimage, base = evm.mapping_slot("0xaf88d065e77c8cC2239327C5EDb3A432268e5831", 52)
    assert preimage == (
        "0x000000000000000000000000af88d065e77c8cc2239327c5edb3a432268e5831"
        "0000000000000000000000000000000000000000000000000000000000000034"
    )
    assert base == "0xeca9b25e580a9539f66a1e310f07d98e6be14b94407490b048d1fe024e73af4f"


def test_eip55_checksums():
    assert evm.to_checksum("0x794a61358d6845594f94dc1db02a252b5b4814ad") == "0x794a61358D6845594F94dc1DB02A252b5b4814aD"
    assert evm.to_checksum("0xaf88d065e77c8cc2239327c5edb3a432268e5831") == "0xaf88d065e77c8cC2239327C5EDb3A432268e5831"


def test_selectors():
    assert evm.selector("getReserveData(address)") == "0x35ea6a75"
    assert evm.selector("getPool()") == "0x026b1d5f"
    assert evm.selector("symbol()") == "0x95d89b41"


def test_word_and_bit_helpers():
    word = "0x0000000000162d96b677fa34fe7e5e0b0000000003cea2840c4e30285542b8b5"
    value = evm.hex_to_int(word)
    assert evm.bits(value, 0, 127) == 1178261207531790554775074997
    assert evm.bits(value, 128, 255) == 26811654683114774957284875
    assert evm.words("0x" + "00" * 32 + "11" * 32) == ["00" * 32, "11" * 32]
    assert evm.push4_selector_present("0x6080604052" + "63" + "5c60da1b" + "00", "implementation()")
