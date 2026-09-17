"""CLI for deepmcpagent: list tools and run an interactive agent session.

Notes:
    - The CLI path uses provider id strings for models (e.g., "openai:gpt-4.1"),
      which `init_chat_model` handles. In code, you can pass a model instance.
    - Model is REQUIRED (no fallback).
"""

from __future__ import annotations

import asyncio
import json
from typing import Annotated, Literal, cast

import typer
from click import Context
from rich.console import Console
from rich.table import Table
from typer.core import TyperCommand

from .agent import build_deep_agent
from .config import HTTPServerSpec, ServerSpec, StdioServerSpec

_SERVER_OPTIONS = {"--http", "--stdio"}
_HTTP_TRANSPORTS = ("http", "streamable-http", "sse")
_HTTPTransport = Literal["http", "streamable-http", "sse"]


class _ServerBlockCommand(TyperCommand):
    """Make documented multi-token server blocks consumable by Click."""

    def parse_args(self, ctx: Context, args: list[str]) -> list[str]:
        encoded_args: list[str] = []
        index = 0
        while index < len(args):
            option = args[index]
            if option not in _SERVER_OPTIONS:
                encoded_args.append(option)
                index += 1
                continue

            block: list[str] = []
            index += 1
            while index < len(args) and not args[index].startswith("--"):
                block.append(args[index])
                index += 1
            encoded_args.extend((option, json.dumps(block)))

        return super().parse_args(ctx, encoded_args)


app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()


def _parse_kv(opts: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in opts:
        if "=" not in item:
            raise typer.BadParameter(f"Expected key=value, got: {item}")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise typer.BadParameter(f"Expected key=value, got: {item}")
        out[key] = value.strip()
    return out


def _decode_blocks(encoded_blocks: list[str]) -> list[list[str]]:
    blocks: list[list[str]] = []
    for encoded in encoded_blocks:
        block: object = json.loads(encoded)
        if not isinstance(block, list) or not all(isinstance(item, str) for item in block):
            raise typer.BadParameter("Server options must contain key=value pairs")
        blocks.append(cast(list[str], block))
    return blocks


def _required(kv: dict[str, str], key: str, option: str) -> str:
    try:
        return kv.pop(key)
    except KeyError:
        raise typer.BadParameter(f"{option} requires {key}=...") from None


def _parse_transport(value: str) -> _HTTPTransport:
    if value not in _HTTP_TRANSPORTS:
        raise typer.BadParameter(
            f"Invalid transport {value!r}; expected http, streamable-http, or sse"
        )
    return cast(_HTTPTransport, value)


def _merge_servers(stdios: list[list[str]], https: list[list[str]]) -> dict[str, ServerSpec]:
    servers: dict[str, ServerSpec] = {}

    # Keep stdio parsing for completeness (see note in StdioServerSpec docstring).
    for block in stdios:
        kv = _parse_kv(block)
        name = _required(kv, "name", "--stdio")
        args = kv.pop("args", "")
        stdio_spec = StdioServerSpec(
            command=_required(kv, "command", "--stdio"),
            args=[item for item in args.split(" ") if item] if args else [],
            env={
                key.split(".", 1)[1]: value for key, value in kv.items() if key.startswith("env.")
            },
            cwd=kv.get("cwd"),
            keep_alive=(kv.get("keep_alive", "true").lower() != "false"),
        )
        servers[name] = stdio_spec

    for block in https:
        kv = _parse_kv(block)
        name = _required(kv, "name", "--http")
        headers = {
            key.split(".", 1)[1]: value for key, value in kv.items() if key.startswith("header.")
        }
        http_spec = HTTPServerSpec(
            url=_required(kv, "url", "--http"),
            transport=_parse_transport(kv.pop("transport", "http")),
            headers=headers,
            auth=kv.get("auth"),
        )
        servers[name] = http_spec

    return servers


@app.command(cls=_ServerBlockCommand)
def list_tools(
    model_id: Annotated[
        str,
        typer.Option(
            "--model-id",
            help="REQUIRED model provider id string (e.g., 'openai:gpt-4.1', "
            "'anthropic:claude-3-opus').",
        ),
    ],
    stdio: Annotated[
        list[str] | None,
        typer.Option("--stdio", help="Block: name=... command=... args='...'"),
    ] = None,
    http: Annotated[
        list[str] | None,
        typer.Option(
            "--http",
            help="Block: name=... url=... [transport=http|streamable-http|sse] [header.X=Y]",
        ),
    ] = None,
    instructions: Annotated[
        str,
        typer.Option("--instructions", help="Optional system prompt override."),
    ] = "",
) -> None:
    """List all MCP tools discovered using the provided server specs."""
    servers = _merge_servers(_decode_blocks(stdio or []), _decode_blocks(http or []))

    async def _run() -> None:
        _graph, loader = await build_deep_agent(
            servers=servers,
            model=model_id,
            instructions=instructions or None,
        )
        infos = await loader.list_tool_info()
        table = Table(title="MCP Tools")
        table.add_column("Tool")
        table.add_column("Description")
        table.add_column("Input Schema")
        for info in infos:
            table.add_row(info.name, info.description or "-", json.dumps(info.input_schema))
        console.print(table)

    asyncio.run(_run())


@app.command(cls=_ServerBlockCommand)
def run(
    model_id: Annotated[
        str,
        typer.Option(
            "--model-id",
            help="REQUIRED model provider id string (e.g., 'openai:gpt-4.1', "
            "'anthropic:claude-3-opus').",
        ),
    ],
    stdio: Annotated[
        list[str] | None,
        typer.Option("--stdio", help="Block: name=... command=... args='...'"),
    ] = None,
    http: Annotated[
        list[str] | None,
        typer.Option(
            "--http",
            help="Block: name=... url=... [transport=http|streamable-http|sse] [header.X=Y]",
        ),
    ] = None,
    instructions: Annotated[
        str,
        typer.Option("--instructions", help="Optional system prompt override."),
    ] = "",
) -> None:
    """Start an interactive agent that uses only MCP tools."""
    servers = _merge_servers(_decode_blocks(stdio or []), _decode_blocks(http or []))

    async def _chat() -> None:
        graph, _loader = await build_deep_agent(
            servers=servers,
            model=model_id,
            instructions=instructions or None,
        )
        console.print("[bold]DeepMCPAgent is ready. Type 'exit' to quit.[/bold]")
        while True:
            try:
                user = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                console.print("\nExiting.")
                break
            if user.lower() in {"exit", "quit"}:
                break
            result = await graph.ainvoke({"messages": [{"role": "user", "content": user}]})
            console.print(result)

    asyncio.run(_chat())
