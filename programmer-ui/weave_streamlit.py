from typing import Optional, Union, Sequence, Dict, Callable, Any
import streamlit as st
import weave
from weave.trace.weave_client import WeaveClient

from programmer.weave_next.api import init_local_client
from programmer.weave_next.weave_query import (
    calls,
    expand_refs,
    get_call,
    expand_json_refs,
)

import weave
from programmer.weave_next.api import init_local_client

ST_HASH_FUNCS: Dict[Any, Callable] = {WeaveClient: lambda x: x._project_id()}


@st.cache_resource
def init_local_weave(db_path: str = "weave.db"):
    return init_local_client(db_path)


@st.cache_resource
def init_remote_weave(project: str):
    return weave.init(project)


@st.cache_data(hash_funcs=ST_HASH_FUNCS)
def cached_calls(
    wc: WeaveClient,
    op_names: Optional[Union[str, Sequence[str]]] = None,
    parent_ids: Optional[Union[str, Sequence[str]]] = None,
    limit: Optional[int] = None,
    expand_refs: Optional[list[str]] = None,
):
    return calls(
        wc,
        op_names=op_names,
        parent_ids=parent_ids,
        limit=limit,
        expand_refs=expand_refs,
    ).to_pandas()


@st.cache_data(hash_funcs=ST_HASH_FUNCS)
def cached_expand_refs(wc: WeaveClient, refs: Sequence[str]):
    return expand_refs(wc, refs).to_pandas()


@st.cache_data(hash_funcs=ST_HASH_FUNCS)
def cached_get_call(wc: WeaveClient, call_id: str):
    return get_call(wc, call_id)


@st.cache_data(hash_funcs=ST_HASH_FUNCS)
def cached_expand_json_refs(wc: WeaveClient, json: dict):
    return expand_json_refs(wc, json)
