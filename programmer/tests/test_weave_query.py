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
