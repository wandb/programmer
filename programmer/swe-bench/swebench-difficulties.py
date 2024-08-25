# Quick script for viewing swebench examples against
# annotated difficulties.

import pandas as pd
import textwrap

swebench_df = pd.read_parquet("swebench-verified.parquet")
anno_df = pd.read_csv("ensembled_annotations_public.csv")
df = swebench_df.merge(anno_df, on="instance_id", how="left")
difficulty_counts = df.groupby(["repo", "difficulty"]).size().unstack(fill_value=0)

# Display the difficulty value counts for each repo
print("Difficulty value counts for each repo:")
print(difficulty_counts)


filtered_df = df[
    (
        df["repo"].isin(["sphinx-doc/sphinx", "sympy/sympy"])
        & (df["difficulty"] == "<15 min fix")
    )
]

# Display the count of filtered examples
print("\nNumber of '<15 min fix' examples from astropy and sympy:")
print(filtered_df["repo"].value_counts())

print(filtered_df)
example = filtered_df.loc[498]
print(example)

# with open("problem.txt", "w") as f:
#     f.write(
#         f"""
# <problem_statement>
# {example["problem_statement"]}
# </problem_statement>
# <hints_text>
# {example["hints_text"]}
# </hints_text>
# """
#     )

# Programmer with new tools passed on 497

# do we need hint text?

with open("problem.txt", "w") as f:
    f.write(
        f"""
<problem_statement>
{example["problem_statement"]}
</problem_statement>
"""
    )
print("FAIL_TO_PASS", example["FAIL_TO_PASS"])
print("PASS_TO_PASS", example["PASS_TO_PASS"])

print("PATCH\n", example["patch"])
print("TEST_PATCH\n", example["test_patch"])

with open("code.patch", "w") as f:
    f.write(example["patch"])
with open("test_code.patch", "w") as f:
    f.write(example["test_patch"])


# Display a few examples
