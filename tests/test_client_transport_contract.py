"""Focused contract test for the FastMCP multi-server client wrapper."""

from fastmcp import Client
from fastmcp.client.transports.config import MCPConfigTransport

from deepmcpagent.clients import FastMCPMulti
from deepmcpagent.config import HTTPServerSpec


def test_client_property_exposes_mcp_config_transport_without_connecting() -> None:
    """Construct and inspect the public client property without network access."""
    multi = FastMCPMulti(
        {"local": HTTPServerSpec(url="http://127.0.0.1:9/mcp")},
    )

    assert isinstance(multi.client, Client)
    assert isinstance(multi.client.transport, MCPConfigTransport)
    assert multi.client.transport.config.mcpServers["local"].url == "http://127.0.0.1:9/mcp"
