from typing import Optional, Union, Sequence, Any
import pandas as pd

from weave.weave_client import WeaveClient
from weave.trace_server.trace_server_interface import (
    CallsQueryReq,
    CallsFilter,
    RefsReadBatchReq,
)


def _construct_calls_filter(
    project_id: str,
    op_names: Optional[Union[str, Sequence[str]]] = None,
    parent_ids: Optional[Union[str, Sequence[str]]] = None,
):
    # TODO: this should have some safety checks

    if op_names is None:
        op_names = []
    elif isinstance(op_names, str):
        op_names = [op_names]
    op_ref_uris = []
    for op_name in op_names:
        if op_name.startswith("weave:///"):
            op_ref_uris.append(op_name)
        else:
            if ":" not in op_name:
                op_name = op_name + ":*"
            op_ref_uris.append(f"weave:///{project_id}/op/{op_name}")

    if parent_ids is None:
        parent_ids = []
    elif isinstance(parent_ids, str):
        parent_ids = [parent_ids]

    return CallsFilter(op_names=op_ref_uris, parent_ids=parent_ids)  # type: ignore


def _server_call_pages(
    wc: WeaveClient,
    filt: CallsFilter,
    limit: Optional[int] = None,
):
    page_index = 0
    page_size = 1000
    remaining = limit
    while True:
        response = wc.server.calls_query(
            CallsQueryReq(
                project_id=wc._project_id(),
                filter=filt,
                offset=page_index * page_size,
                limit=page_size,
            )
        )
        page_data = []
        for v in response.calls:
            v = v.model_dump()
            page_data.append(v)
        if remaining is not None:
            page_data = page_data[:remaining]
            remaining -= len(page_data)
        yield page_data
        if len(page_data) < page_size:
            break
        page_index += 1


def _server_refs(self, refs: Sequence[Union[str, Any]]):
    # Separate refs and non-refs
    ref_uris = []
    non_refs = []
    ref_indices = {}
    for i, item in enumerate(refs):
        if isinstance(item, str) and item.startswith("weave://"):
            ref_uris.append(item)
            if item not in ref_indices:
                ref_indices[item] = []
            ref_indices[item].append(i)
        else:
            non_refs.append((i, item))

    # Process ref URIs
    results = []
    for offset in range(0, len(ref_uris), 1000):
        batch = ref_uris[offset : offset + 1000]
        read_res = self.server.refs_read_batch(RefsReadBatchReq(refs=batch))
        results.extend(read_res.vals)

    # Create a mapping from ref to result
    ref_to_result = dict(zip(ref_uris, results))

    # Combine results in the original order
    final_results: list[Any] = [None] * len(refs)
    for ref, result in ref_to_result.items():
        for index in ref_indices[ref]:
            final_results[index] = result
    for index, item in non_refs:
        final_results[index] = item

    return final_results


class Calls:
    def __init__(self, wc: WeaveClient, filt: CallsFilter):
        self._wc = wc
        self._filt = filt

    def to_pandas(self):
        vals = []
        for page in _server_call_pages(self._wc, self._filt):
            vals.extend(page)
        return pd.json_normalize(vals)


def calls(
    wc: WeaveClient,
    op_names: Optional[Union[str, Sequence[str]]] = None,
    parent_ids: Optional[Union[str, Sequence[str]]] = None,
    limit: Optional[int] = None,
):
    return Calls(wc, _construct_calls_filter(wc._project_id(), op_names, parent_ids))


class Objs:
    def __init__(self, wc: WeaveClient, refs: Sequence[str]):
        self._wc = wc
        self._refs = refs

    def to_pandas(self):
        vals = _server_refs(self._wc, self._refs)
        df = pd.json_normalize(vals)
        df.index = pd.Index(self._refs)
        return df


def expand_refs(wc: WeaveClient, refs: Sequence[str]):
    return Objs(wc, refs)
