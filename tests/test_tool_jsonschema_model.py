"""Focused runtime tests for MCP JSON-Schema conversion."""

from __future__ import annotations

from deepmcpagent.tools import _jsonschema_to_pydantic


def test_jsonschema_conversion_preserves_supported_field_behavior() -> None:
    """Required markers and supported primitive/collection types should survive conversion."""
    model = _jsonschema_to_pydantic(
        {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "count": {"type": "integer"},
                "ratio": {"type": "number"},
                "active": {"type": "boolean"},
                "tags": {"type": "array"},
                "metadata": {"type": "object"},
                "opaque": {},
            },
            "required": ["title", "count", "active"],
        }
    )

    assert model.model_validate(
        {
            "title": "report",
            "count": 2,
            "ratio": 1.5,
            "active": True,
            "tags": ["typed"],
            "metadata": {"source": "mcp"},
            "opaque": 42,
        }
    ).model_dump() == {
        "title": "report",
        "count": 2,
        "ratio": 1.5,
        "active": True,
        "tags": ["typed"],
        "metadata": {"source": "mcp"},
        "opaque": 42,
    }

    try:
        model.model_validate({"title": "report", "count": 2})
    except ValueError:
        pass
    else:
        raise AssertionError("missing required fields must fail validation")


def test_jsonschema_conversion_keeps_payload_fallback_for_empty_properties() -> None:
    """A schema without properties should retain the existing optional payload input."""
    model = _jsonschema_to_pydantic({})

    assert model().model_dump() == {"payload": None}
    assert model(payload={"key": "value"}).model_dump() == {"payload": {"key": "value"}}
