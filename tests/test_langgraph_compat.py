"""Compatibility tests for LangGraph's renamed ReAct system-prompt parameter."""

from __future__ import annotations

import sys
from typing import cast

import pytest
from langchain_core.language_models import LanguageModelLike
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_core.tools import BaseTool

AgentRunnable = Runnable[dict[str, object], dict[str, object]]


def _passthrough(value: dict[str, object]) -> dict[str, object]:
    return value


def _fake_model() -> LanguageModelLike:
    return cast(LanguageModelLike, RunnableLambda(_passthrough))


def _agent_runnable() -> AgentRunnable:
    return RunnableLambda(_passthrough)


async def _no_mcp_tools(_loader: object) -> list[BaseTool]:
    return []


def _fake_multi(_servers: object) -> object:
    return object()


def _use_langgraph_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    import deepmcpagent.agent as agent_module
    from deepmcpagent.tools import MCPToolLoader

    monkeypatch.setitem(sys.modules, "deepagents", None)
    monkeypatch.setattr(agent_module, "FastMCPMulti", _fake_multi)
    monkeypatch.setattr(MCPToolLoader, "get_all_tools", _no_mcp_tools)


async def test_build_deep_agent_passes_prompt_to_legacy_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The declared LangGraph minimum receives the prompt as state_modifier."""
    import deepmcpagent.agent as agent_module

    _use_langgraph_fallback(monkeypatch)
    expected_graph = _agent_runnable()
    captured: dict[str, object] = {}

    def legacy_factory(
        model: LanguageModelLike,
        tools: list[BaseTool],
        *,
        state_modifier: str | None = None,
    ) -> AgentRunnable:
        captured.update(model=model, tools=tools, prompt=state_modifier)
        return expected_graph

    monkeypatch.setattr(agent_module, "create_react_agent", legacy_factory)

    graph, _loader = await agent_module.build_deep_agent(
        servers={}, model=_fake_model(), instructions="legacy system prompt"
    )

    assert graph is expected_graph
    assert captured["tools"] == []
    assert captured["prompt"] == "legacy system prompt"
    assert await graph.ainvoke({"messages": []}) == {"messages": []}


async def test_build_deep_agent_passes_prompt_to_current_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Current LangGraph receives the system prompt through its prompt parameter."""
    import deepmcpagent.agent as agent_module

    _use_langgraph_fallback(monkeypatch)
    expected_graph = _agent_runnable()
    captured: dict[str, object] = {}

    def current_factory(
        model: LanguageModelLike,
        tools: list[BaseTool],
        *,
        prompt: str | None = None,
    ) -> AgentRunnable:
        captured.update(model=model, tools=tools, prompt=prompt)
        return expected_graph

    monkeypatch.setattr(agent_module, "create_react_agent", current_factory)

    graph, _loader = await agent_module.build_deep_agent(
        servers={}, model=_fake_model(), instructions="current system prompt"
    )

    assert graph is expected_graph
    assert captured["tools"] == []
    assert captured["prompt"] == "current system prompt"
    assert await graph.ainvoke({"messages": []}) == {"messages": []}


async def test_build_deep_agent_does_not_hide_factory_type_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compatibility selection must not retry or mask a backend TypeError."""
    import deepmcpagent.agent as agent_module

    _use_langgraph_fallback(monkeypatch)

    def failing_factory(
        model: LanguageModelLike,
        tools: list[BaseTool],
        *,
        prompt: str | None = None,
    ) -> AgentRunnable:
        del model, tools, prompt
        raise TypeError("backend construction failed")

    monkeypatch.setattr(agent_module, "create_react_agent", failing_factory)

    with pytest.raises(TypeError, match="backend construction failed"):
        await agent_module.build_deep_agent(servers={}, model=_fake_model())
