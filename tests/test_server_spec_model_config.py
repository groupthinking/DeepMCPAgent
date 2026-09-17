"""Focused behavior tests for Pydantic server specification configuration."""

import pytest
from pydantic import ValidationError

from deepmcpagent.config import HTTPServerSpec, StdioServerSpec


def test_server_specs_reject_extra_fields() -> None:
    """Both server specification variants reject undeclared fields."""
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        HTTPServerSpec.model_validate({"url": "https://example.com/mcp", "unexpected": True})
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        StdioServerSpec.model_validate({"command": "python", "unexpected": True})


def test_server_specs_construct_and_serialize_valid_values() -> None:
    """Valid server specifications retain their established serialized shape."""
    http = HTTPServerSpec(
        url="https://example.com/mcp",
        transport="streamable-http",
        headers={"Authorization": "Bearer test-token"},
        auth="test-auth",
    )
    stdio = StdioServerSpec(
        command="python",
        args=["-m", "example_server"],
        env={"MODE": "test"},
        cwd="/tmp",
        keep_alive=False,
    )

    assert http.model_dump() == {
        "url": "https://example.com/mcp",
        "transport": "streamable-http",
        "headers": {"Authorization": "Bearer test-token"},
        "auth": "test-auth",
    }
    assert stdio.model_dump() == {
        "command": "python",
        "args": ["-m", "example_server"],
        "env": {"MODE": "test"},
        "cwd": "/tmp",
        "keep_alive": False,
    }
