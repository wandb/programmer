# This is a batch Weave query API. It can move into the Weave library
# if we find it useful.

from typing import Optional, Union, Sequence, Any
import pandas as pd
from weave.trace.weave_client import WeaveClient
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

    results = []
    for offset in range(0, len(ref_uris), 1000):
        batch = ref_uris[offset : offset + 1000]
        read_res = self.server.refs_read_batch(RefsReadBatchReq(refs=batch))
        results.extend(read_res.vals)

    ref_to_result = dict(zip(ref_uris, results))

    final_results: list[Any] = [None] * len(refs)
    for ref, result in ref_to_result.items():
        for index in ref_indices[ref]:
            final_results[index] = result
    for index, item in non_refs:
        final_results[index] = item

    return final_results


def _expand_refs_in_page(wc: WeaveClient, page: list[dict], expand_refs: list[str]):
    # To hack this implementation together, I flatten on each pass instead of dealing
    # with nested keys. This functionality will be available in the server soon,
    # so we can get rid of most of this code.
    flat_page = pd.json_normalize(page).to_dict(orient="records")
    for ref in expand_refs:
        ref_values = [call.get(ref) for call in flat_page]
        expanded_refs = _server_refs(wc, ref_values)
        for call, expanded_ref in zip(flat_page, expanded_refs):
            orig_val = call[ref]
            call[ref] = expanded_ref
            if (
                isinstance(orig_val, str)
                and orig_val.startswith("weave://")
                and isinstance(expanded_ref, dict)
            ):
                expanded_ref["_ref"] = orig_val
        flat_page = pd.json_normalize(flat_page).to_dict(orient="records")
    return flat_page


class Calls:
    def __init__(
        self,
        wc: WeaveClient,
        filt: CallsFilter,
        expand_refs: Optional[list[str]] = None,
    ):
        self._wc = wc
        self._filt = filt
        self._expand_refs = expand_refs or []

    def to_pandas(self):
        vals = []
        for page in _server_call_pages(self._wc, self._filt):
            if self._expand_refs:
                page = _expand_refs_in_page(self._wc, page, self._expand_refs)
            vals.extend(page)
        return pd.json_normalize(vals)


def calls(
    wc: WeaveClient,
    op_names: Optional[Union[str, Sequence[str]]] = None,
    parent_ids: Optional[Union[str, Sequence[str]]] = None,
    limit: Optional[int] = None,
    expand_refs: Optional[list[str]] = None,
):
    return Calls(
        wc, _construct_calls_filter(wc._project_id(), op_names, parent_ids), expand_refs
    )


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


def call(wc: WeaveClient, call_id: str):
    """Return a raw Weave call."""
    response = wc.server.calls_query(
        CallsQueryReq(
            project_id=wc._project_id(),
            filter=CallsFilter(call_ids=[call_id]),
        )
    )
    return response.calls[0].model_dump()


def expand_json_refs(wc: WeaveClient, json: dict):
    """Expand any nested refs in a compound python value"""

    def find_refs(obj):
        refs = []
        if isinstance(obj, dict):
            for value in obj.values():
                refs.extend(find_refs(value))
        elif isinstance(obj, list):
            for item in obj:
                refs.extend(find_refs(item))
        elif isinstance(obj, str) and obj.startswith("weave://"):
            refs.append(obj)
        return refs

    def replace_refs(obj, ref_values):
        if isinstance(obj, dict):
            return {k: replace_refs(v, ref_values) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [replace_refs(item, ref_values) for item in obj]
        elif isinstance(obj, str) and obj.startswith("weave://"):
            return ref_values.get(obj, obj)
        return obj

    refs = find_refs(json)
    if not refs:
        return json

    ref_values = _server_refs(wc, refs)
    ref_dict = {ref: value for ref, value in zip(refs, ref_values)}

    return replace_refs(json, ref_dict)
