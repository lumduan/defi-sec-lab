"""Print the inspection JSON (for learn/web/data/snapshot.json) or the recorded RPC fixtures (for tests).

    python -m inspector.snapshot              > ../web/data/snapshot.json
    python -m inspector.snapshot --fixtures   > tests/fixtures/rpc-fork.json

Fixtures record only (client label, method, params, result). Endpoint URLs are never written.
"""

from __future__ import annotations

import argparse
import json
import sys

import httpx

from . import service
from .config import load_settings


class RecordingTransport(httpx.BaseTransport):
    def __init__(self, fork_url: str) -> None:
        self._inner = httpx.HTTPTransport()
        self._fork_host = httpx.URL(fork_url).host
        self.calls: list[dict] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        response = self._inner.handle_request(request)
        content = response.read()
        payload = json.loads(request.content)
        body = json.loads(content)
        self.calls.append({
            "client": "fork" if request.url.host == self._fork_host else "upstream",
            "method": payload["method"],
            "params": payload["params"],
            "result": body.get("result"),
        })
        return httpx.Response(response.status_code, headers={"content-type": "application/json"}, content=content,
                              request=request)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", choices=["fork", "live"], default="fork")
    parser.add_argument("--fixtures", action="store_true", help="print recorded RPC fixtures instead of the inspection")
    args = parser.parse_args(argv)

    settings = load_settings()
    recorder = RecordingTransport(settings.fork_rpc_url)
    data = service.build(args.source, settings, transport=recorder)
    out = {"schema": "defi-sec-lab/rpc-fixtures@1", "source": args.source, "calls": recorder.calls} if args.fixtures else data
    json.dump(out, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
