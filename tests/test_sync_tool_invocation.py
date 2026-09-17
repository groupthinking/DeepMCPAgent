"""Regression tests for MCP tool execution."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import anyio
from pydantic import BaseModel

from deepmcpagent.tools import _FastMCPTool


class AddArguments(BaseModel):
    """Arguments accepted by the test tool."""

    left: int
    right: int


class FakeMCPClient:
    """Record calls at the external MCP client boundary."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def __aenter__(self) -> FakeMCPClient:
        return self

    async def __aexit__(
        self,
        _exc_type: object | None,
        _exc: object | None,
        _traceback: object | None,
    ) -> None:
        return None

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> SimpleNamespace:
        self.calls.append((name, arguments))
        return SimpleNamespace(data={"sum": 5})


def test_sync_run_forwards_named_arguments_and_normalizes_like_async() -> None:
    """The sync path should preserve MCP arguments and async result normalization."""
    client = FakeMCPClient()
    tool = _FastMCPTool(
        name="add",
        description="Add two numbers",
        args_schema=AddArguments,
        tool_name="math.add",
        client=client,
    )
    arguments = {"left": 2, "right": 3}

    async_result = anyio.run(tool.ainvoke, arguments)
    sync_result = tool.invoke(arguments)

    assert sync_result == async_result == {"sum": 5}
    assert client.calls == [
        ("math.add", {"left": 2, "right": 3}),
        ("math.add", {"left": 2, "right": 3}),
    ]
