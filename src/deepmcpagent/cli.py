"""CLI for deepmcpagent: list tools and run an interactive agent session.

Notes:
    - The CLI path uses provider id strings for models (e.g., "openai:gpt-4.1"),
      which `init_chat_model` handles. In code, you can pass a model instance.
    - Model is REQUIRED (no fallback).
"""

from __future__ import annotations

import asyncio
import json
import shlex
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Annotated, Any, Literal, cast
from urllib.parse import urlparse

import click
import typer
from rich.console import Console
from rich.table import Table

from .agent import build_deep_agent
from .config import HTTPServerSpec, ServerSpec, StdioServerSpec

_HTTP_TRANSPORTS = ("http", "streamable-http", "sse")
_HTTPTransport = Literal["http", "streamable-http", "sse"]
_SERVER_BLOCK_METAVAR = "'KEY=VALUE ...'"
_STDIO_KEYS = {"name", "command", "args", "cwd", "keep_alive"}
_HTTP_KEYS = {"name", "url", "transport", "auth"}
_RAW_ARGS_META_KEY = "deepmcpagent.raw_args"
_CONVERTED_META_KEY = "deepmcpagent.converted_blocks"


class _NativeCommand(click.Command):
    """Keep original Click tokens available without rewriting them."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.pop("rich_markup_mode", None)
        kwargs.pop("rich_help_panel", None)
        super().__init__(*args, **kwargs)

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        ctx.meta[_RAW_ARGS_META_KEY] = tuple(args)
        return super().parse_args(ctx, args)


@dataclass(frozen=True)
class _ServerBlock:
    """A native server option occurrence tagged with its CLI position."""

    position: int
    kind: Literal["http", "stdio"]
    value: str


class _ServerBlockType(click.ParamType[_ServerBlock]):
    """Parse one shell-quoted server block as one native Click option value."""

    name = "server block"

    def __init__(self, kind: Literal["http", "stdio"]) -> None:
        self.kind = kind

    def convert(
        self,
        value: object,
        param: click.Parameter | None,
        ctx: click.Context | None,
    ) -> _ServerBlock:
        if not isinstance(value, str) or not value.strip():
            self.fail("server block must not be empty", param, ctx)

        return _ServerBlock(
            position=_option_position(ctx, self.kind),
            kind=self.kind,
            value=value,
        )


app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()


def _parse_kv(fields: Sequence[str], kind: str) -> dict[str, str]:
    kv: dict[str, str] = {}
    for field in fields:
        if "=" not in field:
            raise ValueError(f"expected key=value, got {field!r}")
        key, value = field.split("=", 1)
        if not key:
            raise ValueError(f"expected a non-empty key, got {field!r}")
        if key in kv:
            raise ValueError(f"duplicate key {key!r}")
        if not _documented_key(kind, key):
            raise ValueError(f"unknown key {key!r} for --{kind}")
        if key.startswith(("env.", "header.")) and not key.split(".", 1)[1].strip():
            raise ValueError(f"{key.split('.', 1)[0]}. suffix must not be empty")
        kv[key] = value
    return kv


def _documented_key(kind: str, key: str) -> bool:
    if kind == "stdio":
        return key in _STDIO_KEYS or key.startswith("env.")
    return key in _HTTP_KEYS or key.startswith("header.")


def _required_non_empty(kv: dict[str, str], key: str, kind: str) -> str:
    try:
        value = kv.pop(key)
    except KeyError:
        raise ValueError(f"--{kind} requires {key}=...") from None
    if not value.strip():
        raise ValueError(f"--{kind} requires a non-empty {key}=...")
    return value


def _parse_stdio(kv: dict[str, str]) -> StdioServerSpec:
    command = _required_non_empty(kv, "command", "stdio")
    args = kv.pop("args", "")
    keep_alive_value = kv.pop("keep_alive", "true")
    if keep_alive_value not in {"true", "false"}:
        raise ValueError("keep_alive must be exactly 'true' or 'false'")
    return StdioServerSpec(
        command=command,
        args=shlex.split(args) if args else [],
        env={key.split(".", 1)[1]: value for key, value in kv.items() if key.startswith("env.")},
        cwd=kv.get("cwd"),
        keep_alive=keep_alive_value == "true",
    )


def _parse_http(kv: dict[str, str]) -> HTTPServerSpec:
    url = _required_non_empty(kv, "url", "http")
    parsed_url = urlparse(url)
    try:
        _ = parsed_url.port
    except ValueError as exc:
        raise ValueError(f"invalid URL: {exc}") from None
    if (
        parsed_url.scheme not in {"http", "https"}
        or not parsed_url.netloc
        or not parsed_url.hostname
        or any(character.isspace() for character in url)
    ):
        raise ValueError("url must be an absolute http:// or https:// URL")
    return HTTPServerSpec(
        url=url,
        transport=_parse_transport(kv.pop("transport", "http")),
        headers={
            key.split(".", 1)[1]: value for key, value in kv.items() if key.startswith("header.")
        },
        auth=kv.get("auth"),
    )


def _parse_transport(value: str) -> _HTTPTransport:
    if value not in _HTTP_TRANSPORTS:
        raise ValueError("transport must be exactly 'http', 'streamable-http', or 'sse'")
    return cast(_HTTPTransport, value)


def _option_position(ctx: click.Context | None, kind: str) -> int:
    if ctx is None:
        return 0
    converted = cast(list[str], ctx.meta.setdefault(_CONVERTED_META_KEY, []))
    ordinal = converted.count(kind)
    converted.append(kind)

    option = f"--{kind}"
    positions: list[int] = []
    raw_args = cast(tuple[str, ...], ctx.meta.get(_RAW_ARGS_META_KEY, ()))
    for index, token in enumerate(raw_args):
        if token == "--":
            break
        if token == option or token.startswith(f"{option}="):
            positions.append(index)
    return positions[ordinal] if ordinal < len(positions) else ordinal


def _merge_servers(*groups: Sequence[_ServerBlock]) -> dict[str, ServerSpec]:
    servers: dict[str, ServerSpec] = {}
    for block in sorted(
        (block for group in groups for block in group), key=lambda item: item.position
    ):
        try:
            fields = shlex.split(block.value)
            kv = _parse_kv(fields, block.kind)
            name = _required_non_empty(kv, "name", block.kind)
            spec: ServerSpec = _parse_stdio(kv) if block.kind == "stdio" else _parse_http(kv)
        except ValueError as exc:
            raise typer.BadParameter(str(exc), param_hint=f"--{block.kind}") from None
        if name in servers:
            raise typer.BadParameter(
                f"duplicate server name {name!r}",
                param_hint=f"--{block.kind}",
            )
        servers[name] = spec
    return servers


_STDIO_OPTION = typer.Option(
    "--stdio",
    metavar=_SERVER_BLOCK_METAVAR,
    click_type=_ServerBlockType("stdio"),
    help="Repeatable quoted block: name=... command=... [args=...] [env.X=Y] [cwd=...] "
    "[keep_alive=true|false]",
)
_HTTP_OPTION = typer.Option(
    "--http",
    metavar=_SERVER_BLOCK_METAVAR,
    click_type=_ServerBlockType("http"),
    help="Repeatable quoted block: name=... url=... [transport=http|streamable-http|sse] "
    "[header.X=Y] [auth=...]",
)


@app.command(cls=_NativeCommand)  # type: ignore[arg-type]
def list_tools(
    model_id: Annotated[
        str,
        typer.Option(
            "--model-id",
            help="REQUIRED model provider id string (e.g., 'openai:gpt-4.1', "
            "'anthropic:claude-3-opus').",
        ),
    ],
    stdio: Annotated[list[_ServerBlock] | None, _STDIO_OPTION] = None,
    http: Annotated[list[_ServerBlock] | None, _HTTP_OPTION] = None,
    instructions: Annotated[
        str,
        typer.Option("--instructions", help="Optional system prompt override."),
    ] = "",
) -> None:
    """List all MCP tools discovered using the provided server specs."""
    servers = _merge_servers(stdio or [], http or [])

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


@app.command(cls=_NativeCommand)  # type: ignore[arg-type]
def run(
    model_id: Annotated[
        str,
        typer.Option(
            "--model-id",
            help="REQUIRED model provider id string (e.g., 'openai:gpt-4.1', "
            "'anthropic:claude-3-opus').",
        ),
    ],
    stdio: Annotated[list[_ServerBlock] | None, _STDIO_OPTION] = None,
    http: Annotated[list[_ServerBlock] | None, _HTTP_OPTION] = None,
    instructions: Annotated[
        str,
        typer.Option("--instructions", help="Optional system prompt override."),
    ] = "",
) -> None:
    """Start an interactive agent that uses only MCP tools."""
    servers = _merge_servers(stdio or [], http or [])

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
