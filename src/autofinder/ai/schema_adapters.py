"""Provider-local JSON Schema adaptations derived from canonical Pydantic schemas."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from autofinder.ai.models import StructuredAIRequest


def groq_strict_schema(request: StructuredAIRequest) -> dict[str, Any]:
    """Return a non-mutating Groq strict-mode schema with every object closed.

    Groq requires every object property to be listed as required and every object
    to set ``additionalProperties`` to false. Nullable Pydantic fields already use
    an ``anyOf`` branch containing ``null``; making them required preserves their
    canonical optional semantics without changing the local Pydantic model.
    """
    schema = deepcopy(request.json_schema)
    _close_objects(schema)
    return schema


def _close_objects(node: Any) -> None:
    """Recursively close object schemas, including definitions and array items."""
    if isinstance(node, list):
        for item in node:
            _close_objects(item)
        return
    if not isinstance(node, dict):
        return
    properties = node.get("properties")
    if isinstance(properties, dict):
        node["required"] = list(properties)
        node["additionalProperties"] = False
    for value in node.values():
        _close_objects(value)



def gemini_schema(request: StructuredAIRequest) -> dict[str, Any]:
    """Return a Gemini-compatible deep copy of the canonical Pydantic schema.

    Gemini's structured-output schema subset enforces fixed string values through
    ``enum``. Pydantic emits a single-value ``Literal`` as ``const``; translate
    only that semantically equivalent string form and leave all other constraints
    (including multi-value enums, nullability, ranges, objects, and arrays) intact.
    """
    schema = deepcopy(request.json_schema)
    _replace_string_consts(schema)
    return schema


def _replace_string_consts(node: Any) -> None:
    """Recursively translate Pydantic string ``const`` nodes to Gemini enums."""
    if isinstance(node, list):
        for item in node:
            _replace_string_consts(item)
        return
    if not isinstance(node, dict):
        return
    if node.get("type") == "string" and isinstance(node.get("const"), str):
        node["enum"] = [node.pop("const")]
    for value in node.values():
        _replace_string_consts(value)
