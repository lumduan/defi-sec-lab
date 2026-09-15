"""Safety properties of the RPC client: read-only allowlist and URL-free errors."""

import httpx
import pytest

from inspector.rpc import RpcClient, RpcError, redact

UPSTREAM_TEST_URL = "https://arb-mainnet.upstream.test/v2/" + "SENSITIVEPATH" * 3


def recording_transport(seen: list) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": "0x1"})

    return httpx.MockTransport(handler)


@pytest.mark.parametrize(
    "method",
    ["eth_sendRawTransaction", "eth_sendTransaction", "eth_sign", "personal_sign", "anvil_setStorageAt",
     "anvil_impersonateAccount", "evm_mine", "hardhat_setBalance", "debug_traceTransaction"],
)
def test_state_changing_and_admin_methods_never_leave_the_process(method):
    seen: list = []
    client = RpcClient("http://fork.test", label="fork", allow_debug=True, transport=recording_transport(seen))
    with pytest.raises(RpcError, match="not allowed"):
        client.call(method, [])
    assert seen == []


def test_debug_trace_call_is_fork_only():
    seen: list = []
    upstream = RpcClient(UPSTREAM_TEST_URL, label="upstream", transport=recording_transport(seen))
    with pytest.raises(RpcError):
        upstream.call("debug_traceCall", [{}, "latest", {}])
    assert seen == []
    fork = RpcClient("http://fork.test", label="fork", allow_debug=True, transport=recording_transport(seen))
    assert fork.call("debug_traceCall", [{}, "latest", {}]) == "0x1"
    assert len(seen) == 1


def _assert_url_free(message: str) -> None:
    assert "SENSITIVEPATH" not in message
    assert "upstream.test" not in message
    assert "://" not in message.replace("<url-redacted>", "")


def test_transport_error_message_has_no_url():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"cannot connect to {request.url}", request=request)

    client = RpcClient(UPSTREAM_TEST_URL, label="upstream", transport=httpx.MockTransport(handler))
    with pytest.raises(RpcError) as info:
        client.call("eth_chainId", [])
    _assert_url_free(str(info.value))
    assert info.value.__suppress_context__  # raised `from None`: the httpx error (with its URL) is not chained


def test_http_status_error_has_no_url():
    client = RpcClient(UPSTREAM_TEST_URL, label="upstream", transport=httpx.MockTransport(lambda r: httpx.Response(403, text=str(r.url))))
    with pytest.raises(RpcError, match="HTTP 403") as info:
        client.call("eth_chainId", [])
    _assert_url_free(str(info.value))


def test_provider_error_text_is_redacted():
    def handler(request: httpx.Request) -> httpx.Response:
        message = f"network not enabled for {UPSTREAM_TEST_URL}; visit https://dashboard.provider.test/apps/42"
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "error": {"code": -32600, "message": message}})

    client = RpcClient(UPSTREAM_TEST_URL, label="upstream", transport=httpx.MockTransport(handler))
    with pytest.raises(RpcError) as info:
        client.call("eth_chainId", [])
    _assert_url_free(str(info.value))
    assert "dashboard.provider.test" not in str(info.value)
    assert "<url-redacted>" in str(info.value) or "<redacted>" in str(info.value)


def test_repr_and_redact_never_show_the_url():
    assert "SENSITIVEPATH" not in repr(RpcClient(UPSTREAM_TEST_URL, label="upstream"))
    assert redact(f"x {UPSTREAM_TEST_URL} y", UPSTREAM_TEST_URL) == "x <redacted> y"


def test_settings_repr_hides_upstream_url(settings):
    assert "FAKEPATH" not in repr(settings)
    assert "<configured>" in repr(settings)
