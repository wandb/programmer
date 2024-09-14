import os
import json
import streamlit as st

from weave_streamlit import cached_calls
from weave_project_picker import get_weave_client


def set_focus_step_id(call_id):
    st.session_state["focus_step_id"] = call_id


def print_step_call(call):
    start_history = call["inputs.state.history"]
    end_history = call["output.history"]
    if isinstance(end_history, float):
        st.write("STEP WITH NO OUTPUT")
        return
    if end_history is None:
        st.write("STEP WITH NO OUTPUT. TODO: Show LLM call here.")
        return
    step_messages = list(end_history)[len(start_history) :]
    assistant_message = step_messages[0]
    tool_response_messages = step_messages[1:]

    if not assistant_message["role"] == "assistant":
        raise ValueError(f"Expected assistant message, got {assistant_message['role']}")

    with st.chat_message("assistant"):
        ended_at = call["ended_at"]
        started_at = call["started_at"]
        duration = ended_at - started_at
        duration_seconds = duration.total_seconds()
        if duration_seconds < 60:
            st.write(f"Duration: {duration_seconds:.2f} seconds")
        else:
            minutes, seconds = divmod(duration_seconds, 60)
            st.write(f"Duration: {int(minutes)} minutes {seconds:.2f} seconds")

        st.write(f"https://wandb.ai/shawn/programmer-sympy/weave/calls/{call.id}")
        st.write(f"State ref:", call["inputs.state._ref"])
        if "content" in assistant_message:
            st.write(assistant_message["content"])
        if "tool_calls" in assistant_message and assistant_message["tool_calls"]:
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
    client = get_weave_client()

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
    client = get_weave_client()

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
