"""Offline test harness: RPC calls are answered from fixtures recorded once from the pinned fork
(python -m inspector.snapshot --fixtures). No network, no anvil, no RPC_URL needed."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from inspector.config import Settings

HERE = Path(__file__).parent
FIXTURES = HERE / "fixtures" / "rpc-fork-504982668.json"
SNAPSHOT = HERE.parents[1] / "web" / "data" / "snapshot.json"
FAKE_FORK_URL = "http://fork.test:8545"
# Deliberately fake upstream endpoint, used to prove the URL never reaches any output.
FAKE_UPSTREAM_URL = "https://arb-mainnet.upstream.test/v2/" + "FAKEPATH" * 4
PIN_NUMBER = 504982668
PIN_HASH = "0xb709093d1bb7a3b51cdecb480ad79e96af60a7aeab4ccf5313216792a11bc079"


def _key(client: str, method: str, params: list) -> tuple[str, str, str]:
    return client, method, json.dumps(params, sort_keys=True)


class ReplayTransport(httpx.BaseTransport):
    def __init__(self, calls: list[dict]) -> None:
        self.table = {_key(c["client"], c["method"], c["params"]): c["result"] for c in calls}
        self.requests: list[tuple[str, str]] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        client = "fork" if request.url.host == "fork.test" else "upstream"
        self.requests.append((client, payload["method"]))
        key = _key(client, payload["method"], payload["params"])
        if key not in self.table:
            error = {"code": -32000, "message": f"no fixture for {client} {payload['method']}"}
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": payload["id"], "error": error})
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": payload["id"], "result": self.table[key]})


@pytest.fixture
def replay() -> ReplayTransport:
    return ReplayTransport(json.loads(FIXTURES.read_text())["calls"])


@pytest.fixture
def settings() -> Settings:
    return Settings(
        fork_rpc_url=FAKE_FORK_URL,
        upstream_rpc_url=FAKE_UPSTREAM_URL,
        fork_block_number=PIN_NUMBER,
        fork_block_hash=PIN_HASH,
        timeout_s=5.0,
    )
