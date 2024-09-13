import streamlit as st

from weave_project_picker import (
    weave_project_picker,
    get_weave_client_description,
    init_weave_client,
)
from page_playground import playground_page
from page_sessions import sessions_page

st.set_page_config(layout="wide")

init_weave_client()

with st.sidebar:
    with st.expander(get_weave_client_description()):
        weave_project_picker()

sessions_pg = st.Page(sessions_page, title="Sessions")
playground_pg = st.Page(playground_page, title="Playground")

pg = st.navigation([sessions_pg, playground_pg])
pg.run()
