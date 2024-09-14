import streamlit as st
import pandas as pd
from weave_project_picker import get_weave_client

from page_sessions import print_run_call

# from programmer.weave_next.weave_query import traces


def split_obj_ref(series: pd.Series):
    expanded = series.str.split("/", expand=True)
    name_version = expanded[6].str.split(":", expand=True)
    result = pd.DataFrame(
        {
            "entity": expanded[3],
            "project": expanded[4],
            "kind": expanded[5],
            "name": name_version[0],
            "version": name_version[1],
        }
    )
    # if len(expanded.columns) > 7:
    #     result["path"] = pd_col_join(expanded.loc[:, expanded.columns > 6], "/")
    return result


class Traces:
    def __init__(self, calls_df: pd.DataFrame):
        calls_df.index = calls_df["id"]
        op_name_fields_df = split_obj_ref(calls_df["op_name"])
        calls_df["op_name.name"] = op_name_fields_df["name"]
        calls_df["op_name.version"] = op_name_fields_df["version"]
        self.df = calls_df

    def roots(self):
        return remove_all_null_columns(self.df[self.df["parent_id"].isna()])

    def children(self, call_id: str):
        return remove_all_null_columns(self.df[self.df["parent_id"] == call_id])


def remove_all_null_columns(df: pd.DataFrame) -> pd.DataFrame:
    return df.dropna(axis=1, how="all")


def select(df: pd.DataFrame, cols):
    result = pd.DataFrame()
    for col in cols:
        if isinstance(col, str):
            if col in df.columns:
                result[col] = df[col]
            else:
                matching_cols = df.filter(regex=col).columns
                for matching_col in matching_cols:
                    result[matching_col] = df[matching_col]
        elif callable(col):
            applied_col = df.apply(col, axis=1)
            if isinstance(applied_col, pd.Series) and applied_col.name:
                result[applied_col.name] = applied_col
            else:
                raise ValueError("Function must return a named Series")
        else:
            raise ValueError("Invalid column specifier")
    return result


@st.cache_data
def load_traces():
    df = pd.read_parquet("eval.parquet")
    return Traces(df)


def calls_table_render(traces: Traces, calls_df: pd.DataFrame):
    sel = st.dataframe(
        calls_df, selection_mode="single-row", on_select="rerun", hide_index=True
    )
    sel_rows = sel.get("selection", {}).get("rows", [])
    if sel_rows:
        sel_view_id = calls_df.index[sel_rows[0]]
        return sel_view_id
    return None


def get_op_name_groups(calls_df: pd.DataFrame):
    partitioned_children = {}
    for _, row in calls_df.iterrows():
        op_name = row["op_name"]
        if op_name not in partitioned_children:
            partitioned_children[op_name] = []
        partitioned_children[op_name].append(row)
    return partitioned_children


def call_children_render(traces: Traces, calls_df: pd.DataFrame, sel_view_id: str):
    children = traces.children(sel_view_id)

    # Partition children into separate dataframes by op_name while preserving order
    partitioned_children = {}
    order = []
    for _, row in children.iterrows():
        op_name = row["op_name"]
        if op_name not in partitioned_children:
            partitioned_children[op_name] = []
            order.append(op_name)
        partitioned_children[op_name].append(row)

    # Convert lists to dataframes and display in original order
    for op_name in order:
        df = remove_all_null_columns(pd.DataFrame(partitioned_children[op_name]))
        st.subheader(f"Operation: {op_name}")
        with st.container():
            calls_table_render(traces, df)


def swebench_page():
    client = get_weave_client()
    st.write(client._project_id())

    st.write("SWEBench")
    call_ids = []
    with st.sidebar:
        eval_call_id1 = st.text_input("Eval Call ID 1")
        if eval_call_id1:
            call_ids.append(eval_call_id1)
            eval_call_id2 = st.text_input("Eval Call ID 2")
            if eval_call_id2:
                call_ids.append(eval_call_id2)

    # if not call_ids:
    #     st.write("No call IDs provided")
    #     return

    # ts = traces(client, call_ids=call_ids)
    # st.write(ts.to_pandas())

    traces = load_traces()
    root_calls = traces.roots()
    root_calls_view = select(root_calls, ["display_name", "output\\..*"])
    sel_view_id = calls_table_render(traces, root_calls_view)
    if sel_view_id:
        children = traces.children(sel_view_id)
        predict_and_score_calls = remove_all_null_columns(
            children[children["op_name.name"] == "Evaluation.predict_and_score"]
        )
        predict_and_score_calls_view = select(
            predict_and_score_calls, ["inputs.example", "output\\..*"]
        )
        sel_predict_and_score_id = calls_table_render(
            traces, predict_and_score_calls_view
        )
        if sel_predict_and_score_id:
            children = traces.children(sel_predict_and_score_id)
            score_call = children[children["op_name.name"] == "score_swebench"].iloc[0]
            st.write(score_call)
            run_call = children[children["op_name.name"] == "Agent.run"].iloc[0]
            steps_df = traces.children(run_call["id"])
            print_run_call(run_call, steps_df)

    # sel = st.dataframe(
    #     root_calls_view, selection_mode="single-row", on_select="rerun", hide_index=True
    # )
    # sel_rows = sel.get("selection", {}).get("rows", [])
    # if sel_rows:
    #     sel_view_id = root_calls_view.index[sel_rows[0]]
    #     sel_call = root_calls.loc[sel_view_id]
    #     children = traces.children(sel_view_id)

    #     # Partition children into separate dataframes by op_name while preserving order
    #     partitioned_children = {}
    #     order = []
    #     for _, row in children.iterrows():
    #         op_name = row["op_name"]
    #         if op_name not in partitioned_children:
    #             partitioned_children[op_name] = []
    #             order.append(op_name)
    #         partitioned_children[op_name].append(row)

    #     # Convert lists to dataframes and display in original order
    #     for op_name in order:
    #         df = remove_all_null_columns(pd.DataFrame(partitioned_children[op_name]))
    #         st.subheader(f"Operation: {op_name}")
    #         st.dataframe(df, hide_index=True)
