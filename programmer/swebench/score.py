from typing import Any
from swebench.harness.test_spec import make_test_spec
from swebench.harness.log_parsers import MAP_REPO_TO_PARSER
from swebench.harness.grading import get_eval_tests_report, get_resolution_status
from swebench.harness.constants import (
    FAIL_TO_PASS,
    KEY_INSTANCE_ID,
    PASS_TO_PASS,
    ResolvedStatus,
    SWEbenchInstance,
)

import weave

from ..io_context import RemoteContainerIOContext


def score_swebench(instance: SWEbenchInstance, model_output):
    patch = model_output["answer"]
    tc = RemoteContainerIOContext(
        "http://localhost:8000",
        "/testbed",
        "source /opt/miniconda3/bin/activate && conda activate testbed && ",
    )

    result: dict[str, Any] = {"patch_successfully_applied": False, "resolved": False}

    ts = make_test_spec(instance)
    container_id = f"sweb.eval.x86_64.{ts.instance_id}"
    with tc.context(container_id):
        print("EVAL SCRIPT\n", ts.eval_script)

        tc.write_file("/tmp/patch.diff", patch)
        patch_result = tc.run_command("git apply -v /tmp/patch.diff")
        if patch_result["exit_code"] != 0:
            print("git apply failed, trying patch")
            patch_result = tc.run_command(
                "patch --batch --fuzz=5 -p1 -i /tmp/patch.diff"
            )
        if patch_result["exit_code"] == 0:
            result["patch_successfully_applied"] = True
        print("PATCH RESULT\n", patch_result)

        tc.write_file("/eval.sh", ts.eval_script)
        test_command_results = tc.run_command("chmod +x /eval.sh && /eval.sh")
        tc_output = test_command_results["output"]

    print("TC OUTPUT\n", tc_output)

    repo = "-".join(
        ts.instance_id.replace("__", "/").split("-")[:-1]
    )  # e.g. scikit-learn/scikit-learn
    log_parser = MAP_REPO_TO_PARSER[repo]
    test_name_to_passfail = log_parser(tc_output)

    eval_ref = {
        KEY_INSTANCE_ID: ts.instance_id,
        FAIL_TO_PASS: ts.FAIL_TO_PASS,
        PASS_TO_PASS: ts.PASS_TO_PASS,
    }

    report = get_eval_tests_report(test_name_to_passfail, eval_ref)
    resolved = get_resolution_status(report) == ResolvedStatus.FULL.value

    result.update({"resolved": resolved, "tests_status": report})

    return result


if __name__ == "__main__":
    import sys
    from .evaluate import load_raw_dataset

    client = weave.init("weavedev-programmereval1")
    call = client.get_call(sys.argv[1])
    instance_id = call.inputs["example"]["instance"]["instance_id"]
    model_output = call.output["model_output"]
    ds = load_raw_dataset("SWE-bench_Verified", "test")
    instance = ds[ds["instance_id"] == instance_id].iloc[0]
    score = score_swebench(instance, model_output)
    print(score)
