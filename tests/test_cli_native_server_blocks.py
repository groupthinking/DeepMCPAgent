"""Regression tests for native repeatable CLI server blocks."""

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
    return importlib.import_module("deepmcpagent.cli")


@pytest.fixture
def agent_calls(monkeypatch: pytest.MonkeyPatch) -> list[Mapping[str, ServerSpec]]:
    captured: list[Mapping[str, ServerSpec]] = []

    class Graph:
        async def ainvoke(self, value: object) -> object:
            return value

    class Loader:
        async def list_tool_info(self) -> list[Any]:
            return []

    async def build_deep_agent(
        *,
        servers: Mapping[str, ServerSpec],
        model: str,
        instructions: str | None = None,
    ) -> tuple[Graph, Loader]:
        del model, instructions
        captured.append(servers)
        return Graph(), Loader()

    monkeypatch.setattr(_cli(), "build_deep_agent", build_deep_agent)
    return captured


def _invoke(command: str, arguments: list[str]) -> Any:
    return runner.invoke(
        _cli().app,
        [command, *arguments],
        input="exit\n" if command == "run" else None,
    )


@pytest.mark.parametrize("command", ["list-tools", "run"])
def test_native_blocks_help_documents_one_quoted_value(command: str) -> None:
    result = _invoke(command, ["--help"])

    assert result.exit_code == 0
    assert "--stdio" in result.output
    assert "--http" in result.output
    assert "KEY=VALUE ..." in result.output
    assert "Repeatable quoted block" in result.output


@pytest.mark.parametrize("command", ["list-tools", "run"])
def test_native_blocks_accept_repeated_mixed_and_attached_values_in_cli_order(
    command: str,
    agent_calls: list[Mapping[str, ServerSpec]],
) -> None:
    result = _invoke(
        command,
        [
            "--http",
            "name=first url=https://example.test/mcp?token=a=b transport=streamable-http "
            "header.Authorization='Bearer a=b' auth=client=a=b",
            "--stdio=name=worker command=python args='-m package --token=a=b' "
            "env.TOKEN=a=b keep_alive=false",
            "--http=name=events url=http://events.example.test/sse transport=sse",
            "--stdio",
            "name=node command=node args='server.js --fixed' cwd=/tmp",
            "--model-id",
            "test:model",
        ],
    )

    assert result.exit_code == 0, result.output
    assert len(agent_calls) == 1
    servers = agent_calls[0]
    assert list(servers) == ["first", "worker", "events", "node"]
    assert servers["first"] == HTTPServerSpec(
        url="https://example.test/mcp?token=a=b",
        transport="streamable-http",
        headers={"Authorization": "Bearer a=b"},
        auth="client=a=b",
    )
    assert servers["worker"] == StdioServerSpec(
        command="python",
        args=["-m", "package", "--token=a=b"],
        env={"TOKEN": "a=b"},
        keep_alive=False,
    )
    assert servers["events"] == HTTPServerSpec(
        url="http://events.example.test/sse",
        transport="sse",
    )
    assert servers["node"] == StdioServerSpec(
        command="node",
        args=["server.js", "--fixed"],
        cwd="/tmp",
    )


@pytest.mark.parametrize("command", ["list-tools", "run"])
@pytest.mark.parametrize("transport", ["http", "streamable-http", "sse"])
def test_native_blocks_accept_only_documented_http_transports(
    command: str,
    transport: str,
    agent_calls: list[Mapping[str, ServerSpec]],
) -> None:
    result = _invoke(
        command,
        [
            f"--http=name=remote url=https://example.test/mcp transport={transport}",
            "--model-id",
            "test:model",
        ],
    )

    assert result.exit_code == 0, result.output
    remote = agent_calls[0]["remote"]
    assert isinstance(remote, HTTPServerSpec)
    assert remote.transport == transport


@pytest.mark.parametrize("command", ["list-tools", "run"])
@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (["--http="], "server block must not be empty"),
        (["--stdio="], "server block must not be empty"),
        (["--http"], "requires an argument"),
        (["--stdio"], "requires an argument"),
        (["--model-id", "test:model", "--unknown"], "No such option '--unknown'"),
        (["--model-id", "test:model", "-x"], "No such option '-x'"),
        (["--model-id", "test:model", "--", "--unknown"], "unexpected extra argument"),
        (
            [
                "--http",
                "name=remote",
                "url=https://example.test/mcp",
                "--model-id",
                "test:model",
            ],
            "unexpected extra argument",
        ),
        (["--http", "url=https://example.test/mcp", "--model-id", "test:model"], "requires name"),
        (["--http", "name=remote", "--model-id", "test:model"], "requires url"),
        (
            ["--http", "name= url=https://example.test/mcp", "--model-id", "test:model"],
            "non-empty name",
        ),
        (["--http", "name=remote url=", "--model-id", "test:model"], "non-empty url"),
        (["--stdio", "command=python", "--model-id", "test:model"], "requires name"),
        (["--stdio", "name=worker", "--model-id", "test:model"], "requires command"),
        (
            ["--stdio", "name= command=python", "--model-id", "test:model"],
            "non-empty name",
        ),
        (
            ["--stdio", "name=worker command=", "--model-id", "test:model"],
            "non-empty command",
        ),
        (
            [
                "--http",
                "name=remote url=https://example.test/mcp extra=value",
                "--model-id",
                "test:model",
            ],
            "unknown key 'extra'",
        ),
        (
            [
                "--stdio",
                "name=worker command=python extra=value",
                "--model-id",
                "test:model",
            ],
            "unknown key 'extra'",
        ),
        (
            [
                "--http",
                "name=remote name=again url=https://example.test/mcp",
                "--model-id",
                "test:model",
            ],
            "duplicate key 'name'",
        ),
        (
            [
                "--http",
                "name=remote url=https://example.test/mcp header.=value",
                "--model-id",
                "test:model",
            ],
            "header. suffix must not be empty",
        ),
        (
            [
                "--stdio",
                "name=worker command=python env.=value",
                "--model-id",
                "test:model",
            ],
            "env. suffix must not be empty",
        ),
        (
            [
                "--stdio",
                "name=worker command=python keep_alive=False",
                "--model-id",
                "test:model",
            ],
            "exactly 'true' or 'false'",
        ),
        (
            [
                "--http",
                "name=remote url=https://example.test/mcp transport=websocket",
                "--model-id",
                "test:model",
            ],
            "exactly 'http', 'streamable-http', or 'sse'",
        ),
        (
            ["--http", "name=remote url=example.test/mcp", "--model-id", "test:model"],
            "absolute http:// or https:// URL",
        ),
        (
            ["--http", "name=remote url=ftp://example.test/mcp", "--model-id", "test:model"],
            "absolute http:// or https:// URL",
        ),
        (
            ["--http", "name=remote url=https://", "--model-id", "test:model"],
            "absolute http:// or https:// URL",
        ),
        (["--http", "name=remote url=https://example.test/mcp"], "Missing option '--model-id'"),
    ],
)
def test_native_blocks_reject_invalid_cli_input_before_building_agent(
    command: str,
    arguments: list[str],
    message: str,
    agent_calls: list[Mapping[str, ServerSpec]],
) -> None:
    result = _invoke(command, arguments)

    assert result.exit_code == 2
    normalized_output = " ".join(result.output.replace("│", "").split())
    assert message.lower() in normalized_output.lower()
    assert agent_calls == []


@pytest.mark.parametrize("command", ["list-tools", "run"])
@pytest.mark.parametrize(
    ("arguments", "second_option"),
    [
        (
            [
                "--http",
                "name=duplicate url=https://example.test/mcp",
                "--stdio",
                "name=duplicate command=python",
            ],
            "--stdio",
        ),
        (
            [
                "--stdio",
                "name=duplicate command=python",
                "--http",
                "name=duplicate url=https://example.test/mcp",
            ],
            "--http",
        ),
    ],
)
def test_native_blocks_reject_duplicate_names_at_second_cli_occurrence(
    command: str,
    arguments: list[str],
    second_option: str,
    agent_calls: list[Mapping[str, ServerSpec]],
) -> None:
    result = _invoke(command, [*arguments, "--model-id", "test:model"])

    assert result.exit_code == 2
    output = " ".join(result.output.split())
    assert "duplicate server name 'duplicate'" in output.lower()
    assert second_option in output
    assert agent_calls == []
