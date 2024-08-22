import pytest

import weave
from weave.weave_client import WeaveClient

from programmer.weave_next.weave_query import calls, expand_refs


def test_weave_query_basic(weave_client: WeaveClient):
    @weave.op
    def add(a: int, b: int) -> int:
        return a + b

    add(1, 2)

    calls_query = calls(weave_client, op_names="add")
    calls_df = calls_query.to_pandas()
    assert len(calls_df) == 1


class Point(weave.Object):
    x: float
    y: float


class NestedObject(weave.Object):
    point: Point
    value: int


@weave.op
def create_point(x: float, y: float) -> Point:
    return Point(x=x, y=y)


@weave.op
def add_points(p1: Point, p2: Point) -> Point:
    return Point(x=p1.x + p2.x, y=p1.y + p2.y)


@weave.op
def create_nested(p: Point, v: int) -> NestedObject:
    return NestedObject(point=p, value=v)


def test_calls_with_expanded_refs(weave_client: WeaveClient):
    p1 = create_point(1.0, 2.0)
    p2 = create_point(3.0, 4.0)
    result = add_points(p1, p2)
    nested = create_nested(result, 42)

    calls_query = calls(
        weave_client, op_names="create_nested", expand_refs=["output", "output.point"]
    )
    calls_df = calls_query.to_pandas()

    assert len(calls_df) == 1
    assert calls_df.iloc[0]["output.value"] == 42
    assert calls_df.iloc[0]["output.point.x"] == 4.0
    assert calls_df.iloc[0]["output.point.y"] == 6.0
