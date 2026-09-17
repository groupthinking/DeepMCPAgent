"""FastMCP client wrapper that supports multiple servers via a single configuration."""

from __future__ import annotations

from collections.abc import Mapping
from types import TracebackType
from typing import Protocol

from fastmcp import Client as FastMCPClient
from mcp.types import Tool

from .config import ServerSpec, servers_to_mcp_config


class MCPClient(Protocol):
    """Client operations exposed by this package across supported FastMCP versions."""

    async def __aenter__(self) -> MCPClient: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def list_tools(self) -> list[Tool]: ...

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, object] | None = None,
    ) -> object: ...


class FastMCPMulti:
    """Create a single FastMCP client wired to multiple servers.

    The client is configured using the `mcpServers` dictionary generated from
    the typed server specifications.

    Args:
        servers: Mapping of server name to server spec.
    """

    def __init__(self, servers: Mapping[str, ServerSpec]) -> None:
        mcp_cfg = {"mcpServers": servers_to_mcp_config(servers)}
        self._client = FastMCPClient(mcp_cfg)

    @property
    def client(self) -> MCPClient:
        """Return the underlying FastMCP client instance."""
        return self._client
