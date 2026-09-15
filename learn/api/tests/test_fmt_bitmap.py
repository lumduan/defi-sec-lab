"""Exact ray formatting and configuration-bitmap decoding (values from notes/00)."""

from inspector import bitmap, fmt

CONFIG_WORD = "0x100000000000000000000103e800ee6b28000d693a4003e8850629041e781d4c"


def test_ray_rate_is_exact_and_raw_first():
    rate = fmt.ray_rate(26811654683114774957284875)
    assert rate["raw"] == "26811654683114774957284875"
    assert rate["fraction"] == "0.026811654683114774957284875"
    assert rate["percent_apr"] == "2.6811654683114774957284875"
    assert rate["percent_apy_derived"] == "2.717432"


def test_ray_index():
    assert fmt.ray_index(1178261207531790554775074997)["value"] == "1.178261207531790554775074997"


def test_fixed_pads_small_values():
    assert fmt.fixed(5, 6) == "0.000005"
    assert fmt.fixed(0, 27) == "0." + "0" * 27


def test_configuration_bitmap():
    decoded = bitmap.decode_configuration(CONFIG_WORD)
    fields = {f["name"]: f for f in decoded["fields"]}
    assert {k: v["raw"] for k, v in fields.items()} == {
        "ltv": 7500,
        "liquidationThreshold": 7800,
        "liquidationBonus": 10500,
        "decimals": 6,
        "reserveFactor": 1000,
        "borrowCap": 225000000,
        "supplyCap": 250000000,
        "liquidationProtocolFee": 1000,
    }
    assert (fields["ltv"]["hex"], fields["liquidationThreshold"]["hex"], fields["liquidationBonus"]["hex"]) == ("1d4c", "1e78", "2904")
    assert [f["name"] for f in decoded["fields"] if f["risk_param"]] == ["ltv", "liquidationThreshold", "liquidationBonus"]
    assert decoded["flags_byte"]["binary"] == "10000101"
    flags = {f["name"]: f["value"] for f in decoded["flags_byte"]["flags"]}
    assert (flags["active"], flags["frozen"], flags["borrowingEnabled"], flags["paused"], flags["flashLoanEnabled"]) == (1, 0, 1, 0, 1)
    holes = {h["bits"]: h["raw"] for h in decoded["holes"]}
    assert holes["168-175"] == 1 and holes["252-252"] == 1
