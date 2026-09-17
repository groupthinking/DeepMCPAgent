"""Deterministic tests for server specification adapters."""

import pytest
from pydantic import ValidationError

from deepmcpagent.config import HTTPServerSpec, StdioServerSpec, servers_to_mcp_config


# Mutation caught: changing the HTTP default transport or emitting empty optional fields.
def test_http_server_conversion_uses_minimal_default_transport() -> None:
    server = HTTPServerSpec(url="https://mcp.example.test/rpc")

    assert servers_to_mcp_config({"primary": server}) == {
        "primary": {
            "transport": "http",
            "url": "https://mcp.example.test/rpc",
        }
    }


# Mutation caught: dropping SSE headers or auth while building the remote-server entry.
def test_sse_server_conversion_preserves_headers_and_auth() -> None:
    server = HTTPServerSpec(
        url="https://events.example.test/sse",
        transport="sse",
        headers={"X-Tenant": "test-tenant", "X-Trace": "fixed-trace"},
        auth="test-auth-profile",
    )

    assert servers_to_mcp_config({"events": server}) == {
        "events": {
            "transport": "sse",
            "url": "https://events.example.test/sse",
            "headers": {"X-Tenant": "test-tenant", "X-Trace": "fixed-trace"},
            "auth": "test-auth-profile",
        }
    }


# Mutation caught: normalizing streamable-http to the plain HTTP transport.
def test_streamable_http_server_conversion_preserves_transport() -> None:
    server = HTTPServerSpec(
        url="https://stream.example.test/mcp",
        transport="streamable-http",
    )

    assert servers_to_mcp_config({"stream": server}) == {
        "stream": {
            "transport": "streamable-http",
            "url": "https://stream.example.test/mcp",
        }
    }


# Mutation caught: changing stdio defaults or serializing an empty env as {}.
def test_stdio_server_conversion_uses_minimal_defaults() -> None:
    server = StdioServerSpec(command="python")

    assert servers_to_mcp_config({"local": server}) == {
        "local": {
            "transport": "stdio",
            "command": "python",
            "args": [],
            "env": None,
            "cwd": None,
            "keep_alive": True,
        }
    }


# Mutation caught: omitting stdio env, cwd, args, or a false keep_alive value.
def test_stdio_server_conversion_preserves_process_configuration() -> None:
    server = StdioServerSpec(
        command="python",
        args=["-m", "example_server", "--fixed"],
        env={"APP_MODE": "test", "REQUEST_ID": "deterministic"},
        cwd="/tmp/example-server",
        keep_alive=False,
    )

    assert servers_to_mcp_config({"local": server}) == {
        "local": {
            "transport": "stdio",
            "command": "python",
            "args": ["-m", "example_server", "--fixed"],
            "env": {"APP_MODE": "test", "REQUEST_ID": "deterministic"},
            "cwd": "/tmp/example-server",
            "keep_alive": False,
        }
    }


@pytest.mark.parametrize(
    ("spec_type", "valid_fields"),
    [
        (HTTPServerSpec, {"url": "https://mcp.example.test/rpc"}),
        (StdioServerSpec, {"command": "python"}),
    ],
)
# Mutation caught: changing the shared server model from extra="forbid" to ignore or allow.
def test_server_specs_reject_forbidden_extra_fields(
    spec_type: type[HTTPServerSpec] | type[StdioServerSpec],
    valid_fields: dict[str, object],
) -> None:
    with pytest.raises(ValidationError) as exc_info:
        spec_type.model_validate({**valid_fields, "timeout_seconds": 30})

    assert [(error["loc"], error["type"]) for error in exc_info.value.errors()] == [
        (("timeout_seconds",), "extra_forbidden")
    ]
