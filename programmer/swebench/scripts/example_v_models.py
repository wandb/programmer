# using existing swe-bench results logged to weave (see ingest dir),
# produce a table with instance_id as rows, and models as columns.
# useful for finding easy / hard examples

import sys
import pandas as pd

import weave

from ...weave_next.weave_query import calls


def main():
    if len(sys.argv) > 1:
        wc = weave.init("weavedev-swebench5")
        c = calls(wc, "Evaluation.predict_and_score", expand_refs=["inputs.example"])
        df = c.to_pandas()

        df.to_parquet("verified.parquet", engine="pyarrow")
    else:
        df = pd.read_parquet("verified.parquet")
    # Pivot the dataframe
    pivot_df = df.pivot(
        index="inputs.example.instance_id",
        columns="inputs.model",
        values="output.model_output.resolved",
    )

    # Extract model names from the column names
    pivot_df.columns = pivot_df.columns.str.extract(r"object/(.+):")[0]

    # Count models with resolved True for each instance
    pivot_df["models_resolved_true"] = pivot_df.apply(lambda row: row.sum(), axis=1)

    # Move the count column to the leftmost position
    cols = pivot_df.columns.tolist()
    cols = cols[-1:] + cols[:-1]
    pivot_df = pivot_df[cols]

    # Sort the pivot table by 'models_resolved_true' in descending order
    pivot_df = pivot_df.sort_values(by="models_resolved_true", ascending=False)  # type: ignore

    # Sort columns by the model that got the most resolved
    model_success_count = pivot_df.sum().sort_values(ascending=False)
    sorted_columns = ["models_resolved_true"] + model_success_count.index.tolist()
    pivot_df = pivot_df[sorted_columns]

    # Display the first few rows of the resulting table
    print(pivot_df.head())

    # Optionally, save the pivot table to a new file
    pivot_df.to_csv("pivot_table.csv")


if __name__ == "__main__":
    main()
