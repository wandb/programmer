import argparse
import sys

import pandas as pd
import weave


splits = {
    "dev": "data/dev-00000-of-00001.parquet",
    "test": "data/test-00000-of-00001.parquet",
    "train": "data/train-00000-of-00001.parquet",
}


def load_raw_dataset(name: str, split: str):
    return pd.read_parquet(
        f"hf://datasets/princeton-nlp/{name}/data/{split}-00000-of-00001.parquet"
    )


def load_weave_dataset(name: str, split: str):
    df = load_raw_dataset(name, split)

    data_list = df.to_dict("records")

    return weave.Dataset(rows=data_list)


def main(dataset_name="SWE-bench_Verified", split="test"):
    valid_datasets = ["SWE-bench", "SWE-bench_Verified", "SWE-bench_Lite"]
    valid_splits = ["dev", "test", "train"]

    if dataset_name not in valid_datasets:
        print(f"Error: Invalid dataset name. Choose from {', '.join(valid_datasets)}")
        sys.exit(1)

    if split not in valid_splits:
        print(f"Error: Invalid split. Choose from {', '.join(valid_splits)}")
        sys.exit(1)

    print(f"Creating dataset: {dataset_name}")
    print(f"Split: {split}")

    weave.init("weavedev-swebench1")

    df = load_raw_dataset(dataset_name, split)

    data_list = df.to_dict("records")

    dataset = weave.Dataset(rows=data_list)

    weave.publish(dataset, f"{dataset_name}_{split}")

    print(f"Dataset '{dataset_name}_{split}' created and saved successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Create a dataset with specified name and split."
    )
    parser.add_argument(
        "--dataset_name",
        choices=["SWE-bench", "SWE-bench_Verified", "SWE-bench_Lite"],
        default="SWE-bench_Verified",
        help="Name of the dataset to create",
    )
    parser.add_argument(
        "--split",
        choices=["dev", "test", "train"],
        default="test",
        help="Split of the dataset to create",
    )

    args = parser.parse_args()
    main(args.dataset_name, args.split)
