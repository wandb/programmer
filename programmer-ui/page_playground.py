import streamlit as st
import copy
import json
import openai


from weave_streamlit import cached_get_call, cached_expand_json_refs
from weave_project_picker import get_weave_client


def write_chat_message(m, key, readonly=False):
    def on_change_content():
        new_value = st.session_state[key]
        st.session_state.playground_state["editable_call"]["inputs"]["messages"][
            m["original_index"]
        ]["content"] = new_value

    with st.chat_message(m["role"]):
        if m.get("content"):
            if readonly:
                st.code(m["content"])
            else:
                st.text_area(
                    "",
                    value=m["content"],
                    label_visibility="collapsed",
                    key=key,
                    on_change=on_change_content,
                )
        if m.get("tool_calls"):
            for t in m["tool_calls"]:
                st.write(t["function"]["name"])
                st.json(
                    {
                        "arguments": t["function"]["arguments"],
                        "response": t.get("response", {}).get("content"),
                    },
                    expanded=True,
                )


def attach_tool_call_responses(messages):
    new_messages = []
    for i, m in enumerate(messages):
        new_m = copy.deepcopy(m)
        new_m["original_index"] = i
        if new_m["role"] == "assistant" and "tool_calls" in new_m:
            new_m["tool_call_responses"] = []
            for t in new_m["tool_calls"]:
                t_id = t["id"]
                for j, t_response in enumerate(messages):
                    if t_response.get("tool_call_id") == t_id:
                        t["response"] = t_response
                        t["response"]["original_index"] = j
                        break
        if "tool_call_id" not in new_m:
            new_messages.append(new_m)
    return new_messages


def playground_page():
    client = get_weave_client()

    with st.sidebar:
        if not st.session_state.get("playground_state"):
            st.session_state.playground_state = {
                "call_id": None,
                "call": None,
                "expanded_call": None,
                "editable_call": None,
            }
        playground_state = st.session_state.playground_state
        call_id = st.text_input("Call ID")
        if not call_id:
            st.error("Please set call ID")
            st.stop()

        # st.write(playground_state)
        if playground_state["expanded_call"] != playground_state["editable_call"]:
            st.warning("Call has been modified")
            if st.button("Restore original call"):
                st.session_state.playground_state["editable_call"] = copy.deepcopy(
                    playground_state["expanded_call"]
                )
                st.rerun()

        if call_id != st.session_state.playground_state["call_id"]:
            st.spinner("Loading call...")
            call = cached_get_call(client, call_id)
            editable_call = cached_expand_json_refs(client, call)
            st.session_state.playground_state = {
                "call_id": call_id,
                "call": call,
                "expanded_call": editable_call,
                "editable_call": copy.deepcopy(editable_call),
            }
            st.rerun()

        call = st.session_state.playground_state["call"]
        editable_call = st.session_state.playground_state["editable_call"]
        if call is None or editable_call is None:
            st.warning("call not yet loaded")
            st.stop()

        st.write(call["op_name"])
        # st.json(call["inputs"])
        # st.json(call["inputs"]["tools"])

        def on_change_temperature():
            st.session_state.playground_state["editable_call"]["inputs"][
                "temperature"
            ] = st.session_state["temperature"]

        st.slider(
            "Temperature",
            min_value=0.0,
            max_value=1.0,
            value=editable_call["inputs"]["temperature"],
            key="temperature",
            on_change=on_change_temperature,
        )

        tools = call["inputs"].get("tools", [])
        if tools:
            st.write("Tools")
            for tool_idx, t in enumerate(tools):
                with st.expander(t["function"]["name"]):

                    def on_change_tool():
                        st.session_state.playground_state["editable_call"]["inputs"][
                            "tools"
                        ][tool_idx] = json.loads(st.session_state[f"tool-{tool_idx}"])
                        st.rerun()

                    st.text_area(
                        "json",
                        value=json.dumps(t, indent=2),
                        height=300,
                        key=f"tool-{tool_idx}",
                        on_change=on_change_tool,
                    )

        def on_change_parallel_tool_calls():
            st.session_state.playground_state["editable_call"]["inputs"][
                "parallel_tool_calls"
            ] = st.session_state["parallel_tool_calls"]

        st.checkbox(
            "Parallel tool calls",
            value=editable_call["inputs"].get("parallel_tool_calls", True),
            key="parallel_tool_calls",
            on_change=on_change_parallel_tool_calls,
        )

    inputs = editable_call["inputs"]
    all_input_messages = inputs["messages"]
    other_inputs = {
        k: v
        for k, v in inputs.items()
        if (k != "messages" and k != "self" and k != "stream")
    }

    tool_call_attached_messages = attach_tool_call_responses(all_input_messages)
    for i, m in enumerate(tool_call_attached_messages):
        write_chat_message(m, f"message-{i}")
    # output = editable_call["output"]["choices"][0]["message"]
    n_choices = st.number_input(
        "Number of choices", value=1, min_value=1, max_value=100
    )
    if st.button("Generate"):
        chat_inputs = {**editable_call["inputs"]}
        # st.json(chat_inputs, expanded=False)
        del chat_inputs["stream"]
        del chat_inputs["self"]
        chat_inputs["n"] = n_choices
        call_resp = openai.chat.completions.create(**chat_inputs).model_dump()

        editable_call["output"] = call_resp
        st.rerun()
        # st.json(response, expanded=False)
        # output = response["choices"][0]["message"]
        # st.json(output)
    response = editable_call["output"]
    st.write("full response")
    st.json(response, expanded=False)
    st.write("**system fingerprint**", response["system_fingerprint"])
    st.write("**usage**", response["usage"])
    for i, choice in enumerate(response["choices"]):
        output = choice["message"]
        st.write(f"Choice {i+1}")
        write_chat_message(output, f"output_message-{i}", readonly=True)

    # all_messages = [*all_input_messages, output]
    # st.json(st.session_state.playground_state, expanded=False)
    # st.json(all_messages, expanded=False)

    # st.write(expanded_call)
