# Streamlit UI for browsing programmer sessions

import pandas as pd
from typing import Optional, Union, Sequence, Dict, Callable, Any
import json
import streamlit as st
import weave
import os
import openai
from weave.trace.weave_client import WeaveClient

from programmer.weave_next.api import init_local_client
from programmer.weave_next.weave_query import (
    calls,
    expand_refs,
    get_call,
    expand_json_refs,
)
from programmer.settings_manager import SettingsManager

st.set_page_config(layout="wide")

ST_HASH_FUNCS: Dict[Any, Callable] = {WeaveClient: lambda x: x._project_id()}


@st.cache_resource
def init_local_weave(db_path: str = "weave.db"):
    return init_local_client(db_path)


@st.cache_resource
def init_remote_weave(project: str):
    return weave.init(project)


def init_from_settings() -> WeaveClient:
    SettingsManager.initialize_settings()
    weave_logging_setting = SettingsManager.get_setting("weave_logging")
    if weave_logging_setting == "off":
        st.error(
            "Weave logging is off. Please set weave_logging to 'on' in settings to use this feature."
        )
        st.stop()
        raise Exception("Should never get here")
    elif weave_logging_setting == "local":
        return init_local_weave(
            os.path.join(SettingsManager.PROGRAMMER_DIR, "weave.db")
        )
    elif weave_logging_setting == "cloud":
        curdir = os.path.basename(os.path.abspath(os.curdir))
        return init_remote_weave(f"programmer-{curdir}")
    else:
        raise ValueError(f"Invalid weave_logging setting: {weave_logging_setting}")


client: WeaveClient = None

# Add sidebar for Weave project configuration
with st.sidebar:
    st.header("Weave Project Configuration")

    # Initialize from settings
    initial_weave_logging = SettingsManager.get_setting("weave_logging")
    initial_project_type = "local" if initial_weave_logging == "local" else "cloud"
    initial_project_path = (
        os.path.join(SettingsManager.PROGRAMMER_DIR, "weave.db")
        if initial_weave_logging == "local"
        else ""
    )
    initial_project_name = (
        f"programmer-{os.path.basename(os.path.abspath(os.curdir))}"
        if initial_weave_logging == "cloud"
        else ""
    )

    project_type = st.radio(
        "Project Type",
        ["local", "cloud"],
        index=0 if initial_project_type == "local" else 1,
    )

    if project_type == "local":
        project_path = st.text_input("Local DB Path", value=initial_project_path)
    else:
        project_name = st.text_input("Cloud Project Name", value=initial_project_name)

    if project_type == "local":
        # SettingsManager.set_setting("weave_logging", "local")
        # SettingsManager.set_setting("weave_db_path", project_path)
        client = init_local_weave(project_path)
        print("C2", client._project_id())
    else:
        # SettingsManager.set_setting("weave_logging", "cloud")
        # SettingsManager.set_setting("weave_project_name", project_name)
        client = init_remote_weave(project_name)
        print("C3", client._project_id())

# Initialize client based on current settings
# client = init_from_settings()
print("CLIENT", client._project_id())


def set_focus_step_id(call_id):
    st.session_state["focus_step_id"] = call_id


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
def cached_expand_json_refs(wc: WeaveClient, json: dict) -> dict:
    return expand_json_refs(wc, json)


def print_step_call(call):
    start_history = call["inputs.state.history"]
    end_history = call["output.history"]
    if isinstance(end_history, float):
        st.write("STEP WITH NO OUTPUT")
        return
    step_messages = list(end_history)[len(start_history) :]
    assistant_message = step_messages[0]
    tool_response_messages = step_messages[1:]

    if not assistant_message["role"] == "assistant":
        raise ValueError(f"Expected assistant message, got {assistant_message['role']}")

    with st.chat_message("assistant"):
        st.write(f"https://wandb.ai/shawn/programmer-sympy/weave/calls/{call.id}")
        st.write(f"State ref:", call["inputs.state._ref"])
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
                    if (
                        f_name == "replace_lines_in_file"
                        or f_name == "read_lines_from_file"
                    ):
                        st.write(f_args)
                    st.text(t_response["content"])

        def set_focus_step_closure():
            set_focus_step_id(call.id)

        try:
            start_snapshot_commit = call[
                "inputs.state.env_snapshot_key.snapshot_info.commit"
            ]
            end_snapshot_commit = call["output.env_snapshot_key.snapshot_info.commit"]

            if start_snapshot_commit is not None and end_snapshot_commit is not None:
                if start_snapshot_commit != end_snapshot_commit:
                    with st.expander(
                        f"git diff {start_snapshot_commit} {end_snapshot_commit}"
                    ):
                        diff_output = os.popen(
                            f"git diff {start_snapshot_commit} {end_snapshot_commit}"
                        ).read()
                        st.code(diff_output, language="diff")

        except KeyError:
            pass

        # st.button("focus", key=f"focus-{call.id}", on_click=set_focus_step_closure)


def print_run_call(
    call,
    steps_df,
):
    st.write("RUN CALL", call.id)
    start_history = steps_df.iloc[0]["inputs.state.history"]
    user_input = start_history[-1]["content"]
    with st.chat_message("user"):
        st.write(user_input)
    for _, step in steps_df.iterrows():
        print_step_call(step)


def print_session_call(session_id):
    runs_df = cached_calls(client, "Agent.run", parent_ids=session_id)
    steps_df = cached_calls(
        client,
        "Agent.step",
        parent_ids=runs_df["id"].tolist(),
        expand_refs=[
            "inputs.state",
            "inputs.state.env_snapshot_key",
            "output",
            "output.env_snapshot_key",
        ],
    )

    for _, run_call_data in runs_df.iterrows():
        run_steps_df = steps_df[steps_df["parent_id"] == run_call_data["id"]]

        print_run_call(
            run_call_data,
            run_steps_df,
        )


def sessions_page():
    session_calls_df = cached_calls(
        client, "session", expand_refs=["inputs.agent_state"]
    )
    if len(session_calls_df) == 0:
        st.error("No programmer sessions found.")
        st.stop()
    session_user_message_df = session_calls_df["inputs.agent_state.history"].apply(
        lambda v: v[-1]["content"]
    )
    with st.sidebar:
        st.header("Session Selection")
        if st.button("Refresh"):
            st.cache_data.clear()
            st.rerun()
        message_ids = {
            f"{cid[-5:]}: {m}": cid
            for cid, m in reversed(
                list(zip(session_calls_df["id"], session_user_message_df))
            )
        }
        sel_message = st.radio("Session", options=message_ids.keys())
        sel_id = None
        if sel_message:
            sel_id = message_ids.get(sel_message)
    if sel_id:
        st.header(f"Session: {sel_id}")
        print_session_call(sel_id)


sessions_pg = st.Page(sessions_page, title="Sessions")


def write_chat_message(m, key):
    with st.chat_message(m["role"]):
        st.text_area("", value=str(m), label_visibility="collapsed", key=key)


def playground_page():
    st.write("Playground")
    call_id = st.text_input("Call ID")
    if not call_id:
        st.error("Please set call ID")
    call = cached_get_call(client, call_id)
    st.write(call["op_name"])

    expanded_call = cached_expand_json_refs(client, call)

    inputs = expanded_call["inputs"]
    all_input_messages = inputs["messages"]
    other_inputs = {
        k: v
        for k, v in inputs.items()
        if (k != "messages" and k != "self" and k != "stream")
    }

    for i, m in enumerate(all_input_messages):
        write_chat_message(m, f"message-{i}")
    output = expanded_call["output"]["choices"][0]["message"]
    if st.button("Generate"):
        chat_inputs = {**other_inputs, "messages": all_input_messages}
        response = openai.chat.completions.create(**chat_inputs).model_dump()
        output = response["choices"][0]["message"]
    write_chat_message(output, "output_message")

    all_messages = [*all_input_messages, output]
    st.json(all_messages, expanded=False)

    # st.write(expanded_call)


playground_pg = st.Page(playground_page, title="Playground")


pg = st.navigation([sessions_pg, playground_pg])
pg.run()
