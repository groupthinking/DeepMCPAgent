"""Focused contract tests for the FastMCP multi-server client wrapper."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, cast, get_type_hints, runtime_checkable

from fastmcp import Client

from deepmcpagent.clients import FastMCPMulti, MCPClient
from deepmcpagent.config import HTTPServerSpec


@runtime_checkable
class _ClientWithTransport(Protocol):
    @property
    def transport(self) -> object: ...


@runtime_checkable
class _MCPConfiguration(Protocol):
    @property
    def mcpServers(self) -> Mapping[str, object]: ...


@runtime_checkable
class _ConfigurationTransport(Protocol):
    @property
    def config(self) -> _MCPConfiguration: ...


@runtime_checkable
class _RemoteServer(Protocol):
    @property
    def url(self) -> str: ...


def test_client_property_exposes_mcp_config_transport_without_connecting() -> None:
    """Construct and inspect the public client property without network access."""
    multi = FastMCPMulti(
        {"local": HTTPServerSpec(url="http://127.0.0.1:9/mcp")},
    )

    client = cast(object, multi.client)
    assert isinstance(client, Client)
    assert isinstance(client, _ClientWithTransport)
    transport = client.transport
    assert type(transport).__name__ == "MCPConfigTransport"
    assert isinstance(transport, _ConfigurationTransport)
    server = transport.config.mcpServers["local"]
    assert isinstance(server, _RemoteServer)
    assert server.url == "http://127.0.0.1:9/mcp"


def test_client_property_return_annotation_resolves_at_runtime() -> None:
    """Keep the public return annotation available to runtime introspection."""
    client_property = cast(property, FastMCPMulti.__dict__["client"])
    getter = client_property.fget
    assert getter is not None
    assert get_type_hints(getter)["return"] is MCPClient
