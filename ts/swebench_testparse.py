import sys
import json
from typing import Dict, Any
from swebench.harness.log_parsers import MAP_REPO_TO_PARSER
from swebench.harness.grading import get_eval_tests_report, get_resolution_status
from swebench.harness.constants import (
    KEY_INSTANCE_ID,
    FAIL_TO_PASS,
    PASS_TO_PASS,
    ResolvedStatus,
)
from swebench.harness.test_spec import make_test_spec

import csv
from pathlib import Path
from typing import List, Dict, Any


def load_test_specs(
    file_path: str = "swebench-verified_test_specs.csv",
) -> List[Dict[str, Any]]:
    # Get the directory of the current script
    current_dir = Path(__file__).parent.resolve()

    # Construct the full path to the CSV file
    full_path = current_dir / file_path

    # Read the CSV file
    test_specs = []
    with open(full_path, "r", newline="") as csvfile:
        csv.field_size_limit(sys.maxsize)
        reader = csv.DictReader(csvfile)
        for row in reader:
            test_specs.append(row)

    return test_specs


def parse_swebench_test(instance_id: str, test_output: str) -> Dict[str, Any]:
    # Load the dataset and get the instance
    ds = load_test_specs()
    instance = [r for r in ds if r["instance_id"] == instance_id]
    if len(instance) == 0:
        raise ValueError(f"Instance {instance_id} not found in dataset")
    ts = instance[0]
    # Parse the repo from instance_id
    repo = "-".join(instance_id.replace("__", "/").split("-")[:-1])

    # Get the appropriate log parser
    log_parser = MAP_REPO_TO_PARSER[repo]

    # Parse the test output
    test_name_to_passfail = log_parser(test_output)

    # Prepare evaluation reference
    eval_ref = {
        KEY_INSTANCE_ID: ts["instance_id"],
        FAIL_TO_PASS: json.loads(ts["FAIL_TO_PASS"]),
        PASS_TO_PASS: json.loads(ts["PASS_TO_PASS"]),
    }

    # Generate report
    report = get_eval_tests_report(test_name_to_passfail, eval_ref)

    # Determine if fully resolved
    resolved = get_resolution_status(report) == ResolvedStatus.FULL.value

    return {"report": report, "resolved": resolved}


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python swebench_testparse.py <instance_id> <test_output_file>")
        sys.exit(1)

    instance_id = sys.argv[1]
    with open(sys.argv[2], "r") as f:
        test_output = f.read()

    result = parse_swebench_test(instance_id, test_output)
    print(json.dumps(result))
