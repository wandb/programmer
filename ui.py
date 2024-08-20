# Streamlit UI for browsing programmer sessions

import pandas as pd
from typing import Optional, Union, Sequence, Dict, Callable, Any
import json
import streamlit as st
import weave
import os
from weave.weave_client import WeaveClient

from programmer.weave_next.weave_query import calls, expand_refs
from programmer.settings_manager import SettingsManager

st.set_page_config(layout="wide")

ST_HASH_FUNCS: Dict[Any, Callable] = {WeaveClient: lambda x: x._project_id()}


@st.cache_resource
def init_local_weave():
    return weave.init_local_client()


@st.cache_resource
def init_remote_weave(project: str):
    return weave.init(project)


def init_from_settings() -> WeaveClient:
    weave_logging_setting = SettingsManager.get_setting("weave_logging")
    if weave_logging_setting == "off":
        st.error(
            "Weave logging is off. Please set weave_logging to 'on' in settings to use this feature."
        )
        st.stop()
    elif weave_logging_setting == "local":
        return init_local_weave()
    elif weave_logging_setting == "cloud":
        curdir = os.path.basename(os.path.abspath(os.curdir))
        return init_remote_weave(f"programmer-{curdir}")
    else:
        raise ValueError(f"Invalid weave_logging setting: {weave_logging_setting}")


client = init_from_settings()


def set_focus_step_id(call_id):
    st.session_state["focus_step_id"] = call_id


@st.cache_data(hash_funcs=ST_HASH_FUNCS)
def cached_calls(
    wc: WeaveClient,
    op_names: Optional[Union[str, Sequence[str]]] = None,
    parent_ids: Optional[Union[str, Sequence[str]]] = None,
    limit: Optional[int] = None,
):
    return calls(wc, op_names=op_names, parent_ids=parent_ids, limit=limit).to_pandas()


@st.cache_data(hash_funcs=ST_HASH_FUNCS)
def cached_expand_refs(wc: WeaveClient, refs: Sequence[str]):
    return expand_refs(wc, refs).to_pandas()


def print_step_call(call, start_state, end_state, start_snapshot_key, end_snapshot_key):
    if isinstance(end_state.history, float):
        st.write("STEP WITH NO OUTPUT")
        return
    step_messages = list(end_state.history)[len(start_state.history) :]
    assistant_message = step_messages[0]
    tool_response_messages = step_messages[1:]

    if not assistant_message["role"] == "assistant":
        raise ValueError(f"Expected assistant message, got {assistant_message['role']}")

    with st.chat_message("assistant"):
        if "content" in assistant_message:
            st.write(assistant_message["content"])
        if "tool_calls" in assistant_message:
            for t in assistant_message["tool_calls"]:
                t_id = t["id"]
                f_name = t["function"]["name"]
                f_args = json.loads(t["function"]["arguments"])
                arg0 = list(f_args.values())[0]
                for t_response in tool_response_messages:
                    if t_response["tool_call_id"] == t_id:
                        break
                else:
                    raise ValueError(f"Tool call response not found for id {t_id}")
                with st.expander(f"{f_name}({arg0}, ...)"):
                    st.text(t_response["content"])

        def set_focus_step_closure():
            set_focus_step_id(call.id)

        if start_snapshot_key is not None and end_snapshot_key is not None:
            if (
                start_snapshot_key["snapshot_info.commit"]
                != end_snapshot_key["snapshot_info.commit"]
            ):
                st.text(
                    f'git diff {start_snapshot_key["snapshot_info.commit"]} {end_snapshot_key["snapshot_info.commit"]}'
                )

        # st.button("focus", key=f"focus-{call.id}", on_click=set_focus_step_closure)


def print_run_call(
    call,
    steps_df,
    step_inputs_state,
    step_outputs,
    steps_input_snapshot_key,
    steps_output_snapshot_key,
):
    start_state = step_inputs_state.iloc[0]
    user_input = start_state["history"][-1]["content"]
    with st.chat_message("user"):
        st.write(user_input)
    for _, step in steps_df.iterrows():
        step_input_state = step_inputs_state.loc[step["inputs.state"]]
        step_output = step_outputs.loc[step["output"]]
        step_input_snapshot_key = steps_input_snapshot_key.loc[step["inputs.state"]]
        step_output_snapshot_key = steps_output_snapshot_key.loc[step["output"]]
        print_step_call(
            step,
            step_input_state,
            step_output,
            step_input_snapshot_key,
            step_output_snapshot_key,
        )


def print_session_call(session_id):
    runs_df = cached_calls(client, "Agent.run", parent_ids=session_id)
    steps_df = cached_calls(client, "Agent.step", parent_ids=runs_df["id"].tolist())
    step_input_state = cached_expand_refs(client, steps_df["inputs.state"].tolist())
    if "env_snapshot_key" in step_input_state.columns:
        step_input_snapshot_key = cached_expand_refs(
            client, step_input_state["env_snapshot_key"].tolist()
        )
    else:
        step_input_snapshot_key = pd.DataFrame()
    # Make step_input_snapshot_key unique by index
    step_input_snapshot_key = step_input_snapshot_key.groupby(level=0).first()
    step_output_state = cached_expand_refs(client, steps_df["output"].tolist())
    if "env_snapshot_key" in step_output_state.columns:
        step_output_snapshot_key = cached_expand_refs(
            client, step_output_state["env_snapshot_key"].tolist()
        )
    else:
        step_output_snapshot_key = pd.DataFrame()
    # Make step_output_snapshot_key unique by index
    step_output_snapshot_key = step_output_snapshot_key.groupby(level=0).first()

    for _, run_call_data in runs_df.iterrows():
        run_steps_df = steps_df[steps_df["parent_id"] == run_call_data["id"]]
        run_steps_inputs_state = step_input_state.loc[run_steps_df["inputs.state"]]
        run_steps_output = step_output_state.loc[run_steps_df["output"]]
        if "env_snapshot_key" in run_steps_inputs_state.columns:
            run_steps_input_snapshot_key = run_steps_inputs_state[
                "env_snapshot_key"
            ].apply(lambda x: None if pd.isna(x) else step_input_snapshot_key.loc[x])
        else:
            run_steps_input_snapshot_key = pd.Series(
                [None] * len(run_steps_inputs_state), index=run_steps_inputs_state.index
            )
        if "env_snapshot_key" in run_steps_output.columns:
            run_steps_output_snapshot_key = run_steps_output["env_snapshot_key"].apply(
                lambda x: None if pd.isna(x) else step_output_snapshot_key.loc[x]
            )
        else:
            run_steps_output_snapshot_key = pd.Series(
                [None] * len(run_steps_output), index=run_steps_output.index
            )

        print_run_call(
            run_call_data,
            run_steps_df,
            run_steps_inputs_state,
            run_steps_output,
            run_steps_input_snapshot_key,
            run_steps_output_snapshot_key,
        )


session_calls_df = cached_calls(client, "session")


session_agent_state_df = cached_expand_refs(
    client, session_calls_df["inputs.agent_state"].tolist()
)
session_user_message_df = session_agent_state_df["history"].apply(
    lambda v: v[-1]["content"]
)


with st.sidebar:
    message_ids = {
        m: cid for cid, m in zip(session_calls_df["id"], session_user_message_df)
    }
    sel_message = st.radio("Session", options=session_user_message_df)
    sel_id = message_ids.get(sel_message)

if sel_id:
    st.header(f"Session: {sel_id}")
    print_session_call(sel_id)
