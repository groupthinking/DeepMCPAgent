"""Deterministic tests for MCP tool schema adapters."""

import pytest
from pydantic import ValidationError

from deepmcpagent.tools import _jsonschema_to_pydantic


# Mutation caught: making required primitive properties optional or mapping their Python types wrong.
def test_required_primitive_properties_have_literal_types_and_no_defaults() -> None:
    model = _jsonschema_to_pydantic(
        {
            "type": "object",
            "properties": {
                "label": {"type": "string"},
                "count": {"type": "integer"},
                "ratio": {"type": "number"},
                "enabled": {"type": "boolean"},
            },
            "required": ["label", "count", "ratio", "enabled"],
        }
    )

    assert {name: field.annotation for name, field in model.model_fields.items()} == {
        "label": str,
        "count": int,
        "ratio": float,
        "enabled": bool,
    }
    assert {name: field.is_required() for name, field in model.model_fields.items()} == {
        "label": True,
        "count": True,
        "ratio": True,
        "enabled": True,
    }
    with pytest.raises(ValidationError) as exc_info:
        model.model_validate({})
    assert [error["loc"] for error in exc_info.value.errors()] == [
        ("label",),
        ("count",),
        ("ratio",),
        ("enabled",),
    ]
    assert model.model_validate(
        {"label": "fixed", "count": 7, "ratio": 2.5, "enabled": True}
    ).model_dump() == {"label": "fixed", "count": 7, "ratio": 2.5, "enabled": True}


# Mutation caught: requiring optional schema properties or swapping primitive/collection mappings.
def test_optional_supported_properties_default_to_none_with_literal_types() -> None:
    model = _jsonschema_to_pydantic(
        {
            "type": "object",
            "properties": {
                "label": {"type": "string"},
                "count": {"type": "integer"},
                "ratio": {"type": "number"},
                "enabled": {"type": "boolean"},
                "tags": {"type": "array"},
                "metadata": {"type": "object"},
            },
        }
    )

    assert {name: field.annotation for name, field in model.model_fields.items()} == {
        "label": str,
        "count": int,
        "ratio": float,
        "enabled": bool,
        "tags": list,
        "metadata": dict,
    }
    assert model.model_validate({}).model_dump() == {
        "label": None,
        "count": None,
        "ratio": None,
        "enabled": None,
        "tags": None,
        "metadata": None,
    }
    assert model.model_validate(
        {
            "label": "fixed",
            "count": 7,
            "ratio": 2.5,
            "enabled": True,
            "tags": ["alpha", "beta"],
            "metadata": {"source": "unit-test"},
        }
    ).model_dump() == {
        "label": "fixed",
        "count": 7,
        "ratio": 2.5,
        "enabled": True,
        "tags": ["alpha", "beta"],
        "metadata": {"source": "unit-test"},
    }


@pytest.mark.parametrize("schema", [{}, {"type": "object", "properties": {}}])
# Mutation caught: returning a zero-field model instead of the payload fallback for an empty schema.
def test_empty_schema_uses_optional_payload_fallback(schema: dict[str, object]) -> None:
    model = _jsonschema_to_pydantic(schema)

    assert list(model.model_fields) == ["payload"]
    assert model.model_fields["payload"].annotation is dict
    assert model.model_fields["payload"].is_required() is False
    assert model.model_validate({}).model_dump() == {"payload": None}
    assert model.model_validate({"payload": {"fixed": 1}}).model_dump() == {"payload": {"fixed": 1}}
