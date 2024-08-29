import os
import argparse
import pandas as pd

from rich import print

import weave

from ..weave_next.api import init_local_client
from ..settings_manager import SettingsManager

from ..swebench.swebench_model import SWEBenchProgrammerModel
from ..swebench.score import score_swebench
from ..config import agent_replace


def main():
    parser = argparse.ArgumentParser(description="Programmer")
    parser.add_argument(
        "--instance_id", type=str, help="The instance id to run", required=True
    )

    # Initialize settings
    SettingsManager.initialize_settings()
    logging_mode = SettingsManager.get_setting("weave_logging")
    if logging_mode == "cloud":
        curdir = os.path.basename(os.path.abspath(os.curdir))
        weave.init(f"programmer-{curdir}")
    elif logging_mode == "local":
        init_local_client(os.path.join(SettingsManager.PROGRAMMER_DIR, "weave.db"))

    args = parser.parse_args()

    df = pd.read_parquet("programmer/swebench/data/swebench-verified.parquet")

    instance_id = args.instance_id
    instance = df[df["instance_id"] == instance_id].iloc[0]
    problem_statement = instance["problem_statement"]

    print("PROBLEM STATEMENT\n", problem_statement)
    print()
    print("SOLUTION\n", instance["patch"])
    print()

    model = SWEBenchProgrammerModel(agent=agent_replace)
    model_output = model.predict(instance)
    score = score_swebench(instance, model_output["answer"])
    print("SCORE\n", score)


if __name__ == "__main__":
    main()
