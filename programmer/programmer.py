import sys
import os
import argparse

from rich import print
from rich.console import Console

import weave

from .agent import AgentState
from .console import Console
from .config import agent
from .environment import (
    environment_session,
    restore_environment,
    GitEnvironment,
    NoopEnvironment,
)
from .settings_manager import SettingsManager

from .git import GitRepo


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
    return AgentState(
        history=state.history
        + [
            {
                "role": "user",
                "content": user_input,
            }
        ],
    )


@weave.op
def session(agent_state: AgentState):
    call = weave.get_current_call()

    session_id = None
    if call:
        session_id = call.id

    git_repo = GitRepo.from_current_dir()
    git_tracking_enabled = SettingsManager.get_setting("git_tracking") == "on"
    if git_tracking_enabled and git_repo:
        env = GitEnvironment(git_repo)
    else:
        env = NoopEnvironment()

    with environment_session(env, session_id):
        while True:
            agent_state = agent.run(agent_state)
            agent_state = user_input_step(agent_state)


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

    # Subparser for the prompt command
    prompt_parser = subparsers.add_parser("prompt", help="Send initial prompt to the LLM")
    prompt_parser.add_argument("prompt_args", nargs=argparse.REMAINDER, help="The prompt to send")

    parser.add_argument(
        "--state", type=str, help="weave ref of the state to begin from"
    )


    # Initialize settings
    SettingsManager.initialize_settings()
    logging_mode = SettingsManager.get_setting("weave_logging")
    if logging_mode == "cloud":
        curdir = os.path.basename(os.path.abspath(os.curdir))
        weave.init(f"programmer-{curdir}")
    elif logging_mode == "local":
        weave.init_local_client()

    args = parser.parse_args()

    if args.command == "settings":
        Console.settings_command(
            [args.action, args.key, args.value]
            if args.value
            else [args.action, args.key]
        )
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

    if args.command == "prompt":
        initial_prompt = " ".join(args.prompt_args)
        print('Initial prompt:', initial_prompt)
    else:
        initial_prompt = input("Initial prompt: ")

    state = AgentState(
        history=[
            {
                "role": "user",
                "content": initial_prompt,
            },
        ],
    )

    session(state)


if __name__ == "__main__":
    main()
