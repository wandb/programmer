import weave
import pandas as pd
from programmer.weave_next.weave_query import traces, Traces


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


if True:
    client = weave.init("weavedev-programmereval1")
    ts = traces(
        client,
        [
            "0191e623-911f-7ac0-9fce-9ff7373eb43f",
            "01919ac8-4fac-7113-8146-53a975de11e6",
        ],
        expand_refs=[
            "inputs.state",
            "inputs.state.env_snapshot_key",
            "output",
            "output.env_snapshot_key",
        ],
    )
    print(len(ts.to_pandas()))

    ts._calls_df.to_parquet("eval.parquet")
else:
    df = pd.read_parquet("eval.parquet")
    ts = Traces(df)
    df.index = df["id"]
    # print(df["op_name"].value_counts())

    trace_roots_df = df[df["parent_id"].isna()]
    trace_roots_df.index = trace_roots_df["trace_id"]

    df["trace_roots_display_name"] = df["trace_id"].map(trace_roots_df["display_name"])
    df["exception_occurred"] = ~df["exception"].isnull()

    op_name_fields_df = split_obj_ref(df["op_name"])
    df["op_name.name"] = op_name_fields_df["name"]
    df["op_name.version"] = op_name_fields_df["version"]

    def get_first_ancestor(row: pd.Series, op_name: str):
        while row["op_name.name"] != op_name:
            if row["parent_id"] is None:
                return {}
            row = df.loc[row["parent_id"]]
        return row

    df["example_id"] = df.apply(
        lambda row: get_first_ancestor(row, "Evaluation.predict_and_score").get(
            "inputs.example"
        ),
        axis=1,
    )
    df["trial_id"] = df.apply(
        lambda row: get_first_ancestor(row, "Evaluation.predict_and_score").get("id"),
        axis=1,
    )
    df["patch_applied"] = df.apply(
        lambda row: get_first_ancestor(row, "Evaluation.predict_and_score").get(
            "output.scores.score_swebench.patch_successfully_applied"
        ),
        axis=1,
    )
    df["resolved"] = df.apply(
        lambda row: get_first_ancestor(row, "Evaluation.predict_and_score").get(
            "output.scores.score_swebench.resolved"
        ),
        axis=1,
    )

    op_name_counts = df.groupby(["trace_roots_display_name", "op_name.name"]).agg(
        {"id": "count", "exception_occurred": "mean"}
    )
    op_name_counts.rename(columns={"id": "count"}, inplace=True)
    # within each top level group (of trace_roots_display_name), sort by count desc
    # op_name_counts.sort_values(by="count", ascending=False, inplace=True, level=1)
    df_sorted = op_name_counts.sort_values(
        by=["trace_roots_display_name", "count"], ascending=[True, False]
    )

    # op_name_counts = df.groupby("trace_roots_display_name")["op_name"].value_counts()
    print(df_sorted)

    run_commands = df[df["op_name.name"] == "run_command"]
    run_commands["command_name"] = run_commands["inputs.command"].str.split(
        " ", expand=True
    )[0]
    command_counts = run_commands.groupby(
        ["trace_roots_display_name", "resolved", "command_name"]
    ).agg(
        {
            "id": "count",
            "exception_occurred": "mean",
            "patch_applied": "sum",
            # "resolved": "sum",
        }
    )
    command_counts.rename(columns={"id": "count"}, inplace=True)
    command_counts = command_counts.sort_values(
        by=["trace_roots_display_name", "resolved", "count"],
        ascending=[True, True, False],
    )
    print(command_counts)

    pytest_commands = run_commands[run_commands["command_name"] == "pytest"]
    command_counts = pytest_commands.groupby(
        ["trace_roots_display_name", "resolved"]
    ).agg({"example_id": "nunique"})
    print(command_counts)

    # print(df["example_id"].value_counts())

    # error_counts = df.groupby("trace_roots_display_name")[
    #     "exception_is_none"
    # ].value_counts()
    # print(error_counts)
