"""Minimal JSON-RPC client with a read-only method allowlist.

Safety properties (each covered by tests/test_rpc.py):
- Only READ_METHODS can be sent. debug_traceCall is additionally allowed on the local fork client only.
  Anything else (eth_sendRawTransaction, anvil_*, evm_*, ...) raises before a single byte leaves the process.
- Error messages never contain the endpoint URL: transport errors are reported by type only, and provider
  error text has every URL redacted.
"""

from __future__ import annotations

import itertools
import re
from typing import Any

import httpx

READ_METHODS = frozenset(
    {
        "eth_chainId",
        "eth_blockNumber",
        "eth_getBlockByNumber",
        "eth_getCode",
        "eth_getStorageAt",
        "eth_call",
        "web3_clientVersion",
    }
)
FORK_ONLY_METHODS = frozenset({"debug_traceCall"})

_URL = re.compile(r"(?i)\b(?:https?|wss?)://[^\s\"'<>]+")


def redact(text: str, *secrets: str | None) -> str:
    """Remove any known secret strings and every URL from a message."""
    for secret in secrets:
        if secret:
            text = text.replace(secret, "<redacted>")
    return _URL.sub("<url-redacted>", text)


class RpcError(Exception):
    """An RPC failure whose message is safe to show (no URLs, no secrets)."""


class RpcClient:
    def __init__(
        self,
        url: str,
        *,
        label: str,
        allow_debug: bool = False,
        timeout: float = 20.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._url = url
        self.label = label
        self.allowed = READ_METHODS | (FORK_ONLY_METHODS if allow_debug else frozenset())
        self._http = httpx.Client(timeout=timeout, transport=transport, follow_redirects=False)
        self._ids = itertools.count(1)

    def __repr__(self) -> str:  # never include the URL
        return f"RpcClient(label={self.label!r})"

    def call(self, method: str, params: list[Any]) -> Any:
        if method not in self.allowed:
            raise RpcError(f"method {method!r} is not allowed on the {self.label} client (read-only allowlist)")
        payload = {"jsonrpc": "2.0", "id": next(self._ids), "method": method, "params": params}
        try:
            response = self._http.post(self._url, json=payload)
        except httpx.HTTPError as exc:
            raise RpcError(f"{self.label} RPC unreachable ({type(exc).__name__})") from None
        if response.status_code != 200:
            raise RpcError(f"{self.label} RPC returned HTTP {response.status_code}")
        try:
            body = response.json()
        except ValueError:
            raise RpcError(f"{self.label} RPC returned a non-JSON response") from None
        if not isinstance(body, dict):
            raise RpcError(f"{self.label} RPC returned an unexpected JSON shape")
        if body.get("error") is not None:
            err = body["error"] if isinstance(body["error"], dict) else {"message": str(body["error"])}
            message = redact(str(err.get("message", ""))[:300], self._url)
            raise RpcError(f"{self.label} RPC error {err.get('code')}: {message}")
        return body.get("result")
