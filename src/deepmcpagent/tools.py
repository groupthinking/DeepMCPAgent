"""MCP tool discovery and conversion to LangChain tools."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import TracebackType
from typing import Protocol, cast

from langchain_core.tools import BaseTool
from pydantic import BaseModel, PrivateAttr, create_model

from .clients import FastMCPMulti


class _MCPClient(Protocol):
    """Operations required from the FastMCP client by a wrapped tool."""

    async def __aenter__(self) -> _MCPClient: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def call_tool(self, name: str, arguments: dict[str, object]) -> object: ...


class _ModelFactory(Protocol):
    """Typed subset of Pydantic's dynamic model factory used here."""

    def __call__(
        self,
        model_name: str,
        /,
        **field_definitions: object | tuple[object, object],
    ) -> type[BaseModel]: ...


_create_model = cast(_ModelFactory, create_model)


@dataclass(frozen=True)
class ToolInfo:
    """Human-friendly metadata for a discovered MCP tool."""

    server_guess: str
    name: str
    description: str
    input_schema: dict[str, object]


def _string_mapping(value: object) -> dict[str, object]:
    """Return string-keyed mapping items from an untrusted schema value."""
    if not isinstance(value, Mapping):
        return {}
    return {key: item for key, item in value.items() if isinstance(key, str)}


def _jsonschema_to_pydantic(schema: Mapping[str, object]) -> type[BaseModel]:
    """Convert a basic JSON Schema dict to a Pydantic model for tool args."""
    properties = _string_mapping(schema.get("properties"))
    required_value = schema.get("required")
    required = (
        {item for item in required_value if isinstance(item, str)}
        if isinstance(required_value, list)
        else set()
    )

    def field_definition(name: str, value: object) -> tuple[object, object]:
        property_schema = _string_mapping(value)
        property_type = property_schema.get("type")
        annotation: object = (
            {
                "string": str,
                "integer": int,
                "number": float,
                "boolean": bool,
                "array": list[object],
                "object": dict[str, object],
            }.get(property_type, object)
            if isinstance(property_type, str)
            else object
        )
        default: object = ... if name in required else None
        return annotation, default

    fields: dict[str, tuple[object, object]] = {
        name: field_definition(name, value) for name, value in properties.items()
    }
    if not fields:
        fields["payload"] = (dict[str, object], None)
    return _create_model("Args", **fields)


class _FastMCPTool(BaseTool):
    """LangChain `BaseTool` wrapper that invokes a FastMCP tool by name."""

    name: str
    description: str
    args_schema: type[BaseModel]

    _tool_name: str = PrivateAttr()
    _client: _MCPClient = PrivateAttr()

    def __init__(
        self,
        *,
        name: str,
        description: str,
        args_schema: type[BaseModel],
        tool_name: str,
        client: _MCPClient,
    ) -> None:
        super().__init__(name=name, description=description, args_schema=args_schema)
        self._tool_name = tool_name
        self._client = client

    async def _arun(self, *args: object, **kwargs: object) -> object:
        """Asynchronously execute the MCP tool via the FastMCP client."""
        if args:
            raise TypeError("MCP tools accept keyword arguments only")
        # Open a session context for each call to be safe across runners.
        async with self._client:
            res = await self._client.call_tool(self._tool_name, kwargs)
        for attr in ("data", "text", "content", "result"):
            if hasattr(res, attr):
                value: object = getattr(res, attr)
                return value
        return res

    def _run(self, *args: object, **kwargs: object) -> object:  # pragma: no cover
        """Synchronous execution path (rarely used)."""
        import anyio

        return anyio.run(lambda: self._arun(*args, **kwargs))


class MCPToolLoader:
    """Discover MCP tools via FastMCP and convert them to LangChain tools."""

    def __init__(self, multi: FastMCPMulti) -> None:
        self._multi = multi

    async def get_all_tools(self) -> list[BaseTool]:
        """Return all available tools as LangChain `BaseTool` instances."""
        c = self._multi.client
        async with c:
            tools = await c.list_tools()
            out: list[BaseTool] = []
            for tool in tools:
                name = tool.name
                desc = getattr(tool, "description", "") or ""
                schema = getattr(tool, "inputSchema", None) or {}
                model = _jsonschema_to_pydantic(schema)
                out.append(
                    _FastMCPTool(
                        name=name,
                        description=desc,
                        args_schema=model,
                        tool_name=name,
                        client=c,
                    )
                )
            return out

    async def list_tool_info(self) -> list[ToolInfo]:
        """Return human-readable tool metadata for introspection or debugging."""
        c = self._multi.client
        async with c:
            tools = await c.list_tools()
            return [
                ToolInfo(
                    server_guess="",
                    name=tool.name,
                    description=getattr(tool, "description", "") or "",
                    input_schema=getattr(tool, "inputSchema", None) or {},
                )
                for tool in tools
            ]
