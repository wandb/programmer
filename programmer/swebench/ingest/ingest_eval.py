import argparse
import os
import sys
import asyncio
import json
import contextvars
from rich import print

import weave
from make_dataset import load_weave_dataset


context_var = contextvars.ContextVar("context", default={})


def load_instance_eval_file(
    experiments_repo_path, dataset_name, model_name, instance_id, file_name
):
    dataset_name_short = dataset_name.split("_")[1].lower()
    file_path = os.path.join(
        experiments_repo_path,
        "evaluation",
        dataset_name_short,
        model_name,
        "logs",
        instance_id,
        file_name,
    )
    print(f"Loading file: {file_path}")

    if os.path.exists(file_path):
        with open(file_path, "r") as file:
            return file.read()
    else:
        return None


def load_instance_eval_from_logs(
    experiments_repo_path, dataset_name, model_name, instance_id
):
    report_json_file = load_instance_eval_file(
        experiments_repo_path,
        dataset_name,
        model_name,
        instance_id,
        "report.json",
    )
    report_json = None
    if report_json_file is not None:
        report_json = json.loads(report_json_file).get(instance_id)
    no_report = False
    if report_json is None:
        no_report = True

    return {
        "patch": load_instance_eval_file(
            experiments_repo_path, dataset_name, model_name, instance_id, "patch.diff"
        ),
        "report": report_json,
        "no_report": no_report,
    }


def load_instance_eval_from_results(
    experiments_repo_path, dataset_name, model_name, instance_id
):
    dataset_name_short = dataset_name.split("_")[1].lower()
    file_path = os.path.join(
        experiments_repo_path,
        "evaluation",
        dataset_name_short,
        model_name,
        "results",
        "results.json",
    )
    with open(file_path, "r") as file:
        results = json.loads(file.read())
    summary = {}
    for k, instance_ids in results.items():
        summary[k] = instance_id in instance_ids

    return summary


class SWEBenchOfflineModel(weave.Model):
    @weave.op
    def predict(self, instance_id: str):
        context = context_var.get()
        experiments_repo_path = context.get("experiments_repo_path")
        dataset_name = context.get("dataset_name")
        return load_instance_eval_from_results(
            experiments_repo_path, dataset_name, self.name, instance_id
        )


@weave.op
def score_from_logs(model_output: dict):
    result = {}
    if model_output.get("report"):
        result.update(model_output["report"])
    result["no_report"] = model_output["no_report"]
    return result


@weave.op
def score(model_output: dict):
    return model_output


def ingest_eval(experiments_repo_path, dataset_name, model_name):
    print(f"Ingesting evaluation logs for:")
    print(f"Dataset: {dataset_name}")
    print(f"Model: {model_name}")
    print(f"From repository: {experiments_repo_path}")

    dataset = load_weave_dataset(dataset_name, "test")
    eval = weave.Evaluation(name=dataset_name, dataset=dataset, scorers=[score])

    context_var.set(
        {
            "experiments_repo_path": experiments_repo_path,
            "dataset_name": dataset_name,
        }
    )

    model = SWEBenchOfflineModel(name=model_name)
    # result, call = asyncio.run(eval.evaluate.call(eval, model))
    result = asyncio.run(eval.evaluate(model))

    print(result)
    # call.set_display_name(model_name)


def ingest_evals(experiments_repo_path, dataset_name):
    dataset_name_short = dataset_name.split("_")[1].lower()
    models_dir = os.path.join(experiments_repo_path, "evaluation", dataset_name_short)
    for model_name in os.listdir(models_dir):
        ingest_eval(experiments_repo_path, dataset_name, model_name)


def main():
    parser = argparse.ArgumentParser(description="Ingest evaluation logs into Weave.")
    parser.add_argument(
        "--experiments_repo_path", help="Path to the experiments repository"
    )
    parser.add_argument(
        "--dataset_name",
        choices=["SWE-bench", "SWE-bench_Verified", "SWE-bench_Lite"],
        default="SWE-bench_Verified",
        help="Name of the dataset",
    )
    parser.add_argument("--model_name", help="Name of the model")

    args = parser.parse_args()

    if not args.experiments_repo_path or not os.path.exists(args.experiments_repo_path):
        print(
            f"Error: Experiments repository path does not exist: {args.experiments_repo_path}"
        )
        sys.exit(1)

    # Initialize Weave
    weave.init("weavedev-swebench5")

    if args.model_name:
        ingest_eval(args.experiments_repo_path, args.dataset_name, args.model_name)
    else:
        ingest_evals(args.experiments_repo_path, args.dataset_name)


if __name__ == "__main__":
    main()
    # from rich import print

    # print(
    #     load_instance_eval(
    #         "/Users/shawnlewis/code/experiments",
    #         "SWE-bench_Verified",
    #         "20240620_sweagent_claude3.5sonnet",
    #         "sympy__sympy-24661",
    #     )
    # )
