"""Build the full inspection for a data source, with a small TTL cache to protect the owner's RPC quota."""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone

import httpx

from . import SCHEMA, stages
from . import sources as src
from .config import Settings, load_settings
from .rpc import RpcClient

CACHE_TTL_S = {"fork": 300.0, "live": 30.0}
_cache: dict[str, tuple[float, dict]] = {}
_locks = {"fork": threading.Lock(), "live": threading.Lock()}


class NotConfigured(Exception):
    """A data source cannot be used with the current configuration (message is safe to show)."""


def build(source: str, settings: Settings | None = None, transport: httpx.BaseTransport | None = None) -> dict:
    s = settings or load_settings()
    fork = RpcClient(s.fork_rpc_url, label="fork", allow_debug=True, timeout=s.timeout_s, transport=transport)
    upstream = (
        RpcClient(s.upstream_rpc_url, label="upstream", timeout=s.timeout_s, transport=transport)
        if s.upstream_rpc_url else None
    )

    if source == "fork":
        if s.fork_block_number is None:
            raise NotConfigured("FORK_BLOCK_NUMBER is not set (fork.env)")
        client, tag = fork, hex(s.fork_block_number)
    elif source == "live":
        if upstream is None:
            raise NotConfigured("RPC_URL is not configured, so the live chain view is unavailable")
        client = upstream
        tag = client.call("eth_blockNumber", [])  # resolve once: every read below uses this exact block
    else:
        raise NotConfigured(f"unknown source {source!r}")

    chain = stages.stage1(client, tag, source, s.fork_block_number, s.fork_block_hash,
                          upstream if source == "fork" else None)
    proxies = stages.stage2(client, tag)
    books = stages.stage3(client, tag, chain["block"]["timestamp"])
    memory = stages.stage4(client, tag, proxies, books, allow_trace=(source == "fork"))

    return {
        "schema": SCHEMA,
        "source": source,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "network": {"name": "Arbitrum One", "chain_id": stages.ARBITRUM_ONE},
        "block": {"tag": tag, "number": chain["block"]["number"], "timestamp_iso": chain["block"]["timestamp_iso"]},
        "asset": {"symbol": "USDC", "address": src.USDC, "kind": "native (Circle-issued)"},
        "citations": src.CITATIONS,
        "stages": [chain, proxies, books, memory],
    }


def get(source: str) -> dict:
    if source not in _locks:
        raise NotConfigured(f"unknown source {source!r}")
    with _locks[source]:
        hit = _cache.get(source)
        if hit and hit[0] > time.monotonic():
            return hit[1]
        data = build(source)
        _cache[source] = (time.monotonic() + CACHE_TTL_S[source], data)
        return data
