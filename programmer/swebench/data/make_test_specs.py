import sys
import pandas as pd
from swebench.harness.test_spec import make_test_spec, TestSpec
import csv
import json
from dataclasses import asdict, fields


def make_test_specs(dataset: pd.DataFrame) -> list[dict]:
    test_specs = []
    for _, row in dataset.iterrows():
        test_spec = make_test_spec(row)  # type: ignore
        test_specs.append(
            {
                "instance_id": test_spec.instance_id,
                "repo": test_spec.repo,
                "version": test_spec.version,
                "repo_script_list": test_spec.repo_script_list,
                "eval_script_list": test_spec.eval_script_list,
                "env_script_list": test_spec.env_script_list,
                "arch": test_spec.arch,
                "FAIL_TO_PASS": test_spec.FAIL_TO_PASS,
                "PASS_TO_PASS": test_spec.PASS_TO_PASS,
                "setup_env_script": test_spec.setup_env_script,
                "eval_script": test_spec.eval_script,
                "install_repo_script": test_spec.install_repo_script,
                "base_image_key": test_spec.base_image_key,
                "env_image_key": test_spec.env_image_key,
                "instance_image_key": test_spec.instance_image_key,
            }
        )
    return test_specs


def dump_test_specs_to_csv(test_specs: list[dict], output_file: str):
    with open(output_file, "w", newline="") as csvfile:
        fieldnames = test_specs[0].keys()
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for spec in test_specs:
            row = spec
            # Convert complex types to JSON strings
            for key, value in row.items():
                if isinstance(value, (dict, list)):
                    row[key] = json.dumps(value)
            writer.writerow(row)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python make_test_specs.py <input_parquet_file>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = input_file.rsplit(".", 1)[0] + "_test_specs.csv"

    # Read the input Parquet file
    dataset = pd.read_parquet(input_file)

    # Generate test specs
    test_specs = make_test_specs(dataset)

    # Dump test specs to CSV
    dump_test_specs_to_csv(test_specs, output_file)

    print(f"Test specs have been written to {output_file}")
