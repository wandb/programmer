from enum import Enum
from typing import TypedDict

import weave

from programmer.tool_calling import generate_json_schema


class Range(TypedDict):
    start: int
    end: int


@weave.op
def merge_ranges(ranges: list[Range]) -> list[Range]:
    """Merge a list of ranges into a single range.

    Args:
        ranges: A list of ranges to merge.

    Returns:
        A list of merged ranges.
    """
    return ranges


def test_list_of_typeddict_schema():
    schema = generate_json_schema(merge_ranges)
    assert schema == {
        "function": {
            "description": "Merge a list of ranges into a single range.",
            "name": "merge_ranges",
            "parameters": {
                "properties": {
                    "ranges": {
                        "description": "A list of ranges to merge.",
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "start": {"type": "integer"},
                                "end": {"type": "integer"},
                            },
                            "required": ["start", "end"],
                        },
                    }
                },
                "required": ["ranges"],
                "type": "object",
            },
        },
        "type": "function",
    }


class Color(Enum):
    RED = 1
    GREEN = 2
    BLUE = 3


@weave.op
def color_name(color: Color) -> str:
    """Get the name of a color.

    Args:
        color: The color to get the name of.

    Returns:
        The name of the color.
    """
    return color.name


def test_enum_schema():
    schema = generate_json_schema(color_name)
    assert schema == {
        "function": {
            "description": "Get the name of a color.",
            "name": "color_name",
            "parameters": {
                "properties": {
                    "color": {
                        "description": "The color to get the name of.",
                        "enum": [1, 2, 3],
                        "type": "integer",
                    }
                },
                "required": ["color"],
                "type": "object",
            },
        },
        "type": "function",
    }
