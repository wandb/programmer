import streamlit as st
import os

from programmer.settings_manager import SettingsManager

from weave.trace.weave_client import WeaveClient

from weave_streamlit import init_local_weave, init_remote_weave


def _reinit_client():
    project_type = st.session_state.get("weave_client-project_type")
    project_path = st.session_state.get("weave_client-local_db_path")
    project_name = st.session_state.get("weave_client-cloud_project_name")
    client = None
    if project_type == "local" and project_path is not None:
        client = init_local_weave(project_path)
    elif project_type == "cloud" and project_name is not None:
        client = init_remote_weave(project_name)
    st.session_state.weave_client = client


def init_weave_client():
    initial_weave_logging = SettingsManager.get_setting("weave_logging")

    initial_project_type = "local" if initial_weave_logging == "local" else "cloud"
    if "weave_client-project_type" not in st.session_state:
        st.session_state["weave_client-project_type"] = initial_project_type

    initial_project_path = os.path.join(SettingsManager.PROGRAMMER_DIR, "weave.db")
    if "weave_client-local_db_path" not in st.session_state:
        st.session_state["weave_client-local_db_path"] = initial_project_path

    initial_project_name = f"programmer-{os.path.basename(os.path.abspath(os.curdir))}"
    if "weave_client-cloud_project_name" not in st.session_state:
        st.session_state["weave_client-cloud_project_name"] = initial_project_name

    _reinit_client()


def weave_project_picker():
    project_type = st.radio(
        "Project Type",
        ["local", "cloud"],
        key="weave_client-project_type",
        on_change=_reinit_client,
    )

    if project_type == "local":
        st.text_input(
            "Local DB Path",
            key="weave_client-local_db_path",
            value=st.session_state["weave_client-local_db_path"],
            on_change=_reinit_client,
        )
    else:
        st.text_input(
            "Cloud Project Name",
            key="weave_client-cloud_project_name",
            # Having this produces a warning on first render, but seems to be necessary
            # for page changes.
            value=st.session_state["weave_client-cloud_project_name"],
            on_change=_reinit_client,
        )


def get_weave_client_description() -> str:
    project_type = st.session_state.get("weave_client-project_type")
    local_db_path = st.session_state.get("weave_client-local_db_path")
    cloud_project_name = st.session_state.get("weave_client-cloud_project_name")
    if project_type == "local" and local_db_path is not None:
        return f"Local: {local_db_path}"
    elif project_type == "cloud" and cloud_project_name is not None:
        return f"Cloud: {cloud_project_name}"
    else:
        return "Not initialized"


def get_weave_client() -> WeaveClient:
    weave_client = st.session_state.get("weave_client")
    if weave_client is None:
        st.error("Please initialize Weave project first")
        st.stop()
    return weave_client
