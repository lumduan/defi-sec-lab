"""End-to-end inspection against recorded fork responses: the numbers of notes/00, snapshot reproducibility,
and the guarantee that the upstream URL never appears in the output."""

import dataclasses
import json

import pytest
from fastapi.testclient import TestClient

from conftest import FAKE_UPSTREAM_URL, SNAPSHOT
from inspector import main, service


def test_fork_inspection_reproduces_notes_00(settings, replay):
    data = service.build("fork", settings, transport=replay)
    chain, proxies, books, memory = data["stages"]

    assert data["block"] == {"tag": "0x1e196c8c", "number": 504982668, "timestamp_iso": "2026-09-14T05:58:31Z"}
    assert {c["id"]: c["status"] for c in chain["checks"]} == {
        "chain_id": "pass", "head_is_pin": "pass", "hash_is_pin": "pass", "hash_is_real_chain": "pass",
    }
    assert chain["client_version"].startswith("anvil/")
    assert chain["block"]["l1_block_number"] == 25973747

    rows = {r["key"]: r for r in proxies["rows"]}
    assert (rows["pool"]["proxy"]["code_size"], rows["pool"]["implementation"]["code_size"]) == (2400, 22442)
    assert (rows["usdc"]["proxy"]["code_size"], rows["usdc"]["implementation"]["code_size"]) == (1852, 23464)
    assert rows["usdc"]["implementation_slot"] == "zeppelinos" and rows["usdc"]["edge"] is True
    assert int(rows["usdc"]["slots"]["eip1967"], 16) == 0
    assert all(rows[k]["implementation_slot"] == "eip1967" for k in ("pool", "atoken", "vtoken", "usdce"))
    assert proxies["registry"]["match"] is True

    assert (books["call"]["returndata_bytes"], books["call"]["word_count"]) == (480, 15)
    fields = {f["name"]: f for f in books["fields"]}
    assert fields["liquidityIndex"]["raw"] == "1178261207531790554775074997"
    assert books["rates"]["supply"]["percent_apr"] == "2.6811654683114774957284875"
    assert books["rates"]["borrow"]["percent_apr"] == "3.6387303323190635207779517"
    assert [(p["name"], p["raw"], p["human"]) for p in books["risk_params"]] == [
        ("ltv", 7500, "75.00 %"), ("liquidationThreshold", 7800, "78.00 %"), ("liquidationBonus", 10500, "105.00 %"),
    ]
    assert fields["aTokenAddress"]["decoded"] == "0x724dc807b04555b71ed48a6896b6F41593b8C637"

    assert memory["proxy"]["revision_in_storage"] == memory["proxy"]["revision_in_code"] == 11
    assert memory["mapping"]["base"] == "0xeca9b25e580a9539f66a1e310f07d98e6be14b94407490b048d1fe024e73af4f"
    assert [c["match"] for c in memory["comparisons"]] == [True, True]
    assert memory["storage"]["low"] == "1178261207531790554775074997"
    assert memory["controls"]["implementation_storage"]["is_zero"] is True
    assert memory["controls"]["trace"]["read_slot"] is True and memory["controls"]["trace"]["value_matches"] is True


def test_output_never_contains_the_upstream_url(settings, replay):
    blob = json.dumps(service.build("fork", settings, transport=replay))
    assert FAKE_UPSTREAM_URL not in blob
    assert "upstream.test" not in blob and "FAKEPATH" not in blob


def test_committed_snapshot_is_reproducible_from_fixtures(settings, replay):
    built = service.build("fork", settings, transport=replay)
    committed = json.loads(SNAPSHOT.read_text())
    built.pop("generated_at")
    committed.pop("generated_at")
    assert built == committed


def test_live_mode_requires_rpc_url(settings, replay):
    with pytest.raises(service.NotConfigured, match="RPC_URL"):
        service.build("live", dataclasses.replace(settings, upstream_rpc_url=None), transport=replay)


def test_fork_mode_without_rpc_url_marks_real_chain_check_not_configured(settings, replay):
    data = service.build("fork", dataclasses.replace(settings, upstream_rpc_url=None), transport=replay)
    check = next(c for c in data["stages"][0]["checks"] if c["id"] == "hash_is_real_chain")
    assert check["status"] == "not_configured" and check["pass"] is None


def test_http_surface(monkeypatch):
    monkeypatch.setattr(service, "get", lambda source: {"schema": "stub", "source": source})
    client = TestClient(main.app)
    assert client.get("/healthz").json() == {"ok": True}
    assert client.get("/v1/inspection").json() == {"schema": "stub", "source": "fork"}
    assert client.get("/v1/inspection?source=live").json()["source"] == "live"
    assert client.get("/v1/inspection?source=../../etc").status_code == 422
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404
