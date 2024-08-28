import sys
import os
import argparse
import subprocess

from rich import print
from rich.console import Console

import weave

from .agent import AgentState, get_commit_message
from .console import Console
from .config import agent, agent_replace
from .environment import (
    environment_session,
    restore_environment,
    get_current_environment,
    GitEnvironment,
    NoopEnvironment,
)
from .weave_next.api import init_local_client
from .settings_manager import SettingsManager
from .tools import RemoteContainerToolContext, tool_context, ToolContext

from .git import GitRepo


class ExitException(Exception):
    pass


@weave.op
def get_user_input():
    return input("User input: ")


@weave.op
def user_input_step(state: AgentState) -> AgentState:
    Console.step_start("user_input", "purple")
    ref = weave.obj_ref(state)
    if ref:
        print("state ref:", ref.uri())
    user_input = get_user_input()
    if user_input.strip() == "/exit":
        raise ExitException("/exit command")
    environment = get_current_environment()
    history = state.history + [
        {
            "role": "user",
            "content": user_input,
        }
    ]
    msg = get_commit_message(history)
    return AgentState(
        history=history,
        env_snapshot_key=environment.make_snapshot(msg),
    )


def make_environment():
    git_repo = GitRepo.from_current_dir()
    git_tracking_enabled = SettingsManager.get_setting("git_tracking") == "on"
    if git_tracking_enabled and git_repo:
        env = GitEnvironment(git_repo)
    else:
        env = NoopEnvironment()
    return env


@weave.op
def session(agent_state: AgentState):
    call = weave.get_current_call()

    session_id = None
    if call:
        session_id = call.id

    env = make_environment()
    msg = get_commit_message(agent_state.history)

    with environment_session(env, session_id):
        agent_state = AgentState(
            history=agent_state.history, env_snapshot_key=env.make_snapshot(msg)
        )
        while True:
            agent_state = agent_replace.run(agent_state)
            try:
                agent_state = user_input_step(agent_state)
            except ExitException as e:
                print("Exiting")
                return


def eval_swebench(tc: RemoteContainerToolContext, instance, patch):
    from swebench.harness.test_spec import make_test_spec
    from swebench.harness.log_parsers import MAP_REPO_TO_PARSER
    from swebench.harness.grading import get_eval_tests_report, get_resolution_status
    from swebench.harness.constants import (
        FAIL_TO_PASS,
        KEY_INSTANCE_ID,
        PASS_TO_PASS,
        ResolvedStatus,
    )

    result = {"patch_successfully_applied": False, "resolved": False}

    ts = make_test_spec(instance)
    tc.start_container(f"sweb.eval.x86_64.{instance.instance_id}")
    print("EVAL SCRIPT\n", ts.eval_script)

    tc.write_file("/tmp/patch.diff", patch)
    patch_result = tc.run_command("git apply -v /tmp/patch.diff")
    if patch_result["exit_code"] == 0:
        result["patch_successfully_applied"] = True
    print("PATCH RESULT\n", patch_result)

    tc.write_file("/eval.sh", ts.eval_script)
    test_command_results = tc.run_command("chmod +x /eval.sh && /eval.sh")
    tc_output = test_command_results["output"]
    repo = "-".join(
        instance.instance_id.replace("__", "/").split("-")[:-1]
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


def main():
    parser = argparse.ArgumentParser(description="Programmer")
    subparsers = parser.add_subparsers(dest="command")

    # Subparser for the settings command
    settings_parser = subparsers.add_parser("settings", help="Manage settings")
    settings_parser.add_argument(
        "action", choices=["get", "set"], help="Action to perform"
    )
    settings_parser.add_argument("key", help="The setting key")
    settings_parser.add_argument("value", nargs="?", help="The value to set")

    ui_parser = subparsers.add_parser("ui", help="Run the local UI")

    # Subparser for the prompt command
    prompt_parser = subparsers.add_parser(
        "prompt", help="Send initial prompt to the LLM"
    )
    prompt_parser.add_argument(
        "prompt_args", nargs=argparse.REMAINDER, help="The prompt to send"
    )

    parser.add_argument(
        "--state", type=str, help="weave ref of the state to begin from"
    )
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

    if args.command == "settings":
        Console.settings_command(
            [args.action, args.key, args.value]
            if args.value
            else [args.action, args.key]
        )
        return
    elif args.command == "ui":
        module_path = os.path.abspath(__file__)
        module_dir = os.path.dirname(module_path)
        ui_path = os.path.join(module_dir, "..", "programmer-ui", "ui.py")
        subprocess.run(["streamlit", "run", ui_path])
        return
    elif args.command == "prompt":
        # Handled later.
        pass

    # log to local sqlite db for now

    Console.welcome()

    if args.state:
        state = weave.ref(args.state).get()
        if state.env_snapshot_key:
            environment = restore_environment(state.env_snapshot_key)

    # if args.command == "prompt":
    #     initial_prompt = " ".join(args.prompt_args)
    #     print("Initial prompt:", initial_prompt)
    # else:
    #     initial_prompt = input("Initial prompt: ")
    import pandas as pd

    df = pd.read_parquet("programmer/swe-bench/swebench-verified.parquet")

    instance_id = args.instance_id
    instance = df[df["instance_id"] == instance_id].iloc[0]
    problem_statement = instance["problem_statement"]

    print("PROBLEM STATEMENT\n", problem_statement)
    print()
    print("SOLUTION\n", instance["patch"])
    print()

    tc = RemoteContainerToolContext(
        "http://localhost:8000",
        "/testbed",
        "source /opt/miniconda3/bin/activate && conda activate testbed && ",
    )

    initial_prompt = f"""You are in a checkout of the a git repo. Please identify and fix the issue described in the problem statement.

<problem_statement>
{problem_statement}
</problem_statement>"""

    state = AgentState(
        history=[
            {
                "role": "user",
                "content": initial_prompt,
            },
        ],
    )

    tc.start_container(f"sweb.eval.x86_64.{instance_id}")
    tc.run_command("")

    with tool_context(tc):
        agent_replace.run(state)

    print()
    print("SOLUTION\n", instance["patch"])
    print()
    answer = tc.run_command("git diff")
    print("ANSWER\n", answer)

    print()
    print("EVALUATING")
    print()
    report = eval_swebench(tc, instance, answer["output"])
    print("REPORT")
    print(report)


if __name__ == "__main__":
    main()
