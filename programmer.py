import sys
import os
import argparse

from rich import print
from rich.console import Console


import weave

from agent import AgentState
from console import Console
from config import agent


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
    while True:
        agent_state = agent.run(agent_state)
        agent_state = user_input_step(agent_state)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Programmer")
    parser.add_argument(
        "--state", type=str, help="weave ref of the state to begin from"
    )

    curdir = os.path.basename(os.path.abspath(os.curdir))

    # log to local sqlite db for now
    # weave.init(f"programmerdev1-{curdir}")
    weave.init_local_client()

    Console.welcome()

    args, remaining = parser.parse_known_args()
    if args.state:
        state = weave.ref(args.state).get()
    else:
        if len(sys.argv) < 2:
            initial_prompt = input("Initial prompt: ")
        else:
            initial_prompt = " ".join(sys.argv[1:])
            print("Initial prompt:", initial_prompt)

        state = AgentState(
            history=[
                {
                    "role": "user",
                    "content": initial_prompt,
                },
            ],
        )

    session(state)
