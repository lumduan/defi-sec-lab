"""Runtime settings, read from the environment when a request is built. Nothing is hardcoded.

RPC_URL is a secret: an upstream endpoint that usually embeds an API key. The code only uses it to open
connections. It is never logged, never returned, never placed in an error message, and never rendered by repr().
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, repr=False)
class Settings:
    fork_rpc_url: str
    upstream_rpc_url: str | None
    fork_block_number: int | None
    fork_block_hash: str | None
    timeout_s: float

    def __repr__(self) -> str:
        return (
            f"Settings(fork_rpc_url={self.fork_rpc_url!r}, "
            f"upstream_rpc_url={'<configured>' if self.upstream_rpc_url else None}, "
            f"fork_block_number={self.fork_block_number}, fork_block_hash={self.fork_block_hash!r})"
        )


def load_settings() -> Settings:
    block = os.environ.get("FORK_BLOCK_NUMBER", "").strip()
    block_hash = os.environ.get("FORK_BLOCK_HASH", "").strip().lower()
    return Settings(
        fork_rpc_url=os.environ.get("FORK_RPC_URL", "http://anvil:8545").strip(),
        upstream_rpc_url=os.environ.get("RPC_URL", "").strip() or None,
        fork_block_number=int(block) if block.isdigit() else None,
        fork_block_hash=block_hash or None,
        timeout_s=float(os.environ.get("INSPECTOR_RPC_TIMEOUT_S", "20")),
    )
