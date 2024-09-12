import sys
import os
import argparse
import subprocess

from rich import print
from rich.console import Console

from typing import Any, Optional

import weave

from .agent import Agent, AgentState, get_commit_message
from .console import Console, console
from .config import (
    # agent_4o_replace,
    # agent_texteditor_4o_basic,
    # agent_texteditor_o1_gpt4o,
    # agent_texteditor_o1_o1preview,
    get_config_by_name,
)
from .environment import (
    environment_session,
    restore_environment,
    get_current_environment,
    GitEnvironment,
    NoopEnvironment,
)
from .weave_next.api import init_local_client
from .settings_manager import SettingsManager

from .git import GitRepo


@weave.op
def get_user_input():
    return input("User input: ")


@weave.op
def user_input_step(state: AgentState) -> AgentState:
    Console.step_start("user_input", "purple")
    # Printing this is ugly
    # ref = weave.obj_ref(state)
    # if ref:
    #     print("state ref:", ref.uri())
    user_input = get_user_input()
    history = state.history + [
        {
            "role": "user",
            "content": user_input,
        }
    ]
    return state.with_history(history)


def settings_command(command_args):
    if len(command_args) < 2:
        console.print("[red]Invalid settings command[/red]")
        return
    action = command_args[0]
    key = command_args[1]
    if action == "get":
        value = SettingsManager.get_setting(key)
        if value is not None:
            console.print(f"{key} = {value}")
        else:
            console.print(f"[red]Setting '{key}' not found[/red]")
    elif action == "set" and len(command_args) == 3:
        value = command_args[2]
        SettingsManager.set_setting(key, value)
        console.print(f"[green]Setting '{key}' updated to '{value}'[/green]")
    else:
        console.print("[red]Invalid settings command[/red]")


def make_environment():
    git_repo = GitRepo.from_current_dir()
    git_tracking_enabled = SettingsManager.get_setting("git_tracking") == "on"
    if git_tracking_enabled and git_repo:
        env = GitEnvironment(git_repo)
    else:
        env = NoopEnvironment()
    return env


@weave.op
def session(agent: Agent, agent_state: AgentState):
    call = weave.get_current_call()

    session_id = None
    if call:
        session_id = call.id

    env = make_environment()

    with environment_session(env, session_id):
        agent_state = agent_state.with_history(agent_state.history)
        while True:
            result = agent.run(agent_state)
            agent_state = result["state"]
            agent_state = user_input_step(agent_state)


def programmer():
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
        settings_command(
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

    if args.state:
        state = weave.ref(args.state).get()
        if state.env_snapshot_key:
            environment = restore_environment(state.env_snapshot_key)

    agent_name = SettingsManager.get_setting("agent")
    if not agent_name:
        raise ValueError(
            "No agent name set. Please set the agent name in the settings."
        )
    agent = get_config_by_name(agent_name)
    if not agent:
        raise ValueError(
            f"Agent {agent_name} not found. Please set a valid agent name in the settings."
        )

    Console.welcome(agent_name=agent.name)

    if args.command == "prompt":
        initial_prompt = " ".join(args.prompt_args)
        print("Initial prompt:", initial_prompt)
    else:
        initial_prompt = input("Initial prompt: ")

    state = agent.initial_state(
        [
            {
                "role": "user",
                "content": initial_prompt,
            },
        ]
    )

    session(agent, state)


def main():
    try:
        programmer()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
