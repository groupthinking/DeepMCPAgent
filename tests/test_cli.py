"""Regression tests for the documented DeepMCPAgent command-line interface."""

from __future__ import annotations

import importlib
from collections.abc import Mapping
from types import ModuleType
from typing import Any

import pytest
from typer.testing import CliRunner

from deepmcpagent.config import HTTPServerSpec, ServerSpec, StdioServerSpec

runner = CliRunner()


def _cli() -> ModuleType:
    """Import the CLI lazily so broken command declarations fail inside each test."""
    return importlib.import_module("deepmcpagent.cli")


def _stub_agent_builder(monkeypatch: pytest.MonkeyPatch) -> list[Mapping[str, ServerSpec]]:
    captured: list[Mapping[str, ServerSpec]] = []

    class Loader:
        async def list_tool_info(self) -> list[Any]:
            return []

    async def build_deep_agent(
        *,
        servers: Mapping[str, ServerSpec],
        model: str,
        instructions: str | None = None,
    ) -> tuple[object, Loader]:
        del model, instructions
        captured.append(servers)
        return object(), Loader()

    monkeypatch.setattr(_cli(), "build_deep_agent", build_deep_agent)
    return captured


@pytest.mark.parametrize("command", ["list-tools", "run"])
def test_command_help_renders_server_block_options(command: str) -> None:
    result = runner.invoke(_cli().app, [command, "--help"])

    assert result.exit_code == 0
    assert "--stdio" in result.output
    assert "--http" in result.output
    assert "--model-id" in result.output


def test_list_tools_parses_repeated_documented_server_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _stub_agent_builder(monkeypatch)

    result = runner.invoke(
        _cli().app,
        [
            "list-tools",
            "--stdio",
            "name=python-server",
            "command=python",
            "args=-m example.server",
            "env.MODE=test",
            "--stdio",
            "name=node-server",
            "command=node",
            "args=server.js --fixed",
            "keep_alive=false",
            "--http",
            "name=plain",
            "url=https://plain.example.test/mcp",
            "transport=http",
            "header.Authorization=Bearer test-token",
            "--http",
            "name=events",
            "url=https://events.example.test/sse",
            "transport=sse",
            "--model-id",
            "test:model",
        ],
    )

    assert result.exit_code == 0, result.output
    assert len(captured) == 1
    servers = captured[0]
    assert servers["python-server"] == StdioServerSpec(
        command="python",
        args=["-m", "example.server"],
        env={"MODE": "test"},
    )
    assert servers["node-server"] == StdioServerSpec(
        command="node",
        args=["server.js", "--fixed"],
        keep_alive=False,
    )
    assert servers["plain"] == HTTPServerSpec(
        url="https://plain.example.test/mcp",
        transport="http",
        headers={"Authorization": "Bearer test-token"},
    )
    assert servers["events"] == HTTPServerSpec(
        url="https://events.example.test/sse",
        transport="sse",
    )


@pytest.mark.parametrize("transport", ["http", "streamable-http", "sse"])
def test_list_tools_accepts_documented_http_transports(
    monkeypatch: pytest.MonkeyPatch,
    transport: str,
) -> None:
    captured = _stub_agent_builder(monkeypatch)

    result = runner.invoke(
        _cli().app,
        [
            "list-tools",
            "--http",
            "name=remote",
            "url=https://example.test/mcp",
            f"transport={transport}",
            "--model-id",
            "test:model",
        ],
    )

    assert result.exit_code == 0, result.output
    remote = captured[0]["remote"]
    assert isinstance(remote, HTTPServerSpec)
    assert remote.transport == transport


def test_list_tools_rejects_invalid_http_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _stub_agent_builder(monkeypatch)

    result = runner.invoke(
        _cli().app,
        [
            "list-tools",
            "--http",
            "name=remote",
            "url=https://example.test/mcp",
            "transport=websocket",
            "--model-id",
            "test:model",
        ],
    )

    assert result.exit_code == 2
    normalized_output = " ".join(result.output.split())
    assert "websocket" in normalized_output
    assert "streamable-http, or sse" in normalized_output
    assert captured == []


def test_list_tools_rejects_malformed_key_value_pair(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _stub_agent_builder(monkeypatch)

    result = runner.invoke(
        _cli().app,
        [
            "list-tools",
            "--http",
            "name=remote",
            "not-a-key-value-pair",
            "url=https://example.test/mcp",
            "--model-id",
            "test:model",
        ],
    )

    assert result.exit_code == 2
    assert "Expected key=value, got: not-a-key-value-pair" in result.output
    assert captured == []


@pytest.mark.parametrize("malformed", ["=value", "   =value"])
def test_list_tools_rejects_empty_keys(
    monkeypatch: pytest.MonkeyPatch,
    malformed: str,
) -> None:
    captured = _stub_agent_builder(monkeypatch)

    result = runner.invoke(
        _cli().app,
        [
            "list-tools",
            "--http",
            "name=remote",
            malformed,
            "url=https://example.test/mcp",
            "--model-id",
            "test:model",
        ],
    )

    assert result.exit_code == 2
    assert f"Expected key=value, got: {malformed}" in result.output
    assert captured == []
