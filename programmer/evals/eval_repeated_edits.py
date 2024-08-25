import tempfile
import os
import time
from typing import TypedDict, Callable
from contextlib import contextmanager

import weave

from ..agent import AgentState, Agent
from ..config import agent, agent_replace


# @pytest.fixture
@contextmanager
def tempdir():
    with tempfile.TemporaryDirectory() as tempdir:
        orig_dir = os.getcwd()
        os.chdir(tempdir)
        try:
            yield tempdir
        finally:
            os.chdir(orig_dir)


class EvalEditMemoryConfig(TypedDict):
    n_lines: int


def eval_edit_memory_step(
    agent: Agent,
    prompt: str,
    cur_expected_lines: list[str],
    modify_expected_fn: Callable,
):
    state = AgentState(
        history=[
            {
                "role": "user",
                "content": prompt,
            },
        ],
    )
    next_state = agent.run(state)

    expected_lines = modify_expected_fn(cur_expected_lines)

    with open("file.txt", "r") as f:
        file_contents = f.read()
        file_lines = file_contents.split("\n")
        print("file.txt\texpected")
        print(f"len={len(file_lines)}\tlen={len(expected_lines)}")
        for i in range(len(expected_lines)):
            print(f"{file_lines[i]}\t{expected_lines[i]}")
        correct = file_contents == "\n".join(expected_lines)

    return correct, next_state, expected_lines


@weave.op
def eval_edit_memory(config: EvalEditMemoryConfig, agent: Agent):
    with tempdir():
        lines = []
        n_alpha = 10
        num_per_alpha = config["n_lines"] // n_alpha
        for i in range(config["n_lines"]):
            lines.append(f"{chr(65 + i // num_per_alpha)}{i % num_per_alpha}")

        with open("file.txt", "w") as f:
            prev_file_contents = "\n".join(lines)
            f.write(prev_file_contents)

        state = AgentState()

        n_correct = 0
        for prompt, modify_expected_fn in [
            (
                "file.txt contains lines like 'C4', 'D8' etc. Replace lines 'A7' through 'B4' (inclusive) with 'X\\nY\\n'.",
                lambda lines: lines[: lines.index("A7")]
                + ["X", "Y"]
                + lines[lines.index("B4") + 1 :],
            ),
            (
                "Actually that edit was wrong. Replace them with 'Z\nZZ\nZZZ\n' instead.",
                lambda lines: lines[: lines.index("X")]
                + ["Z", "ZZ", "ZZZ"]
                + lines[lines.index("Y") + 1 :],
            ),
        ]:
            state = AgentState(
                history=state.history
                + [
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
            )
            state = agent.run(state)

            lines = modify_expected_fn(lines)

            with open("file.txt", "r") as f:
                file_contents = f.read().strip()
                if file_contents == prev_file_contents:
                    return {
                        "correct_steps": n_correct,
                        "reason": "no change",
                        "error_details": "",
                    }
                prev_file_contents = file_contents

                file_lines = file_contents.split("\n")
                correct = file_contents == "\n".join(lines)
                if not correct:
                    error_details = []
                    error_details.append("Incorrect edit")
                    error_details.append("file.txt\texpected")
                    error_details.append(f"len={len(file_lines)}\tlen={len(lines)}")
                    for i in range(len(lines)):
                        try:
                            file_lines_i = file_lines[i]
                        except IndexError:
                            file_lines_i = None
                        try:
                            lines_i = lines[i]
                        except IndexError:
                            lines_i = None
                        line_correct = file_lines_i == lines_i
                        line_correct_str = "✅" if line_correct else "❌"
                        error_details.append(
                            f"{line_correct_str} {file_lines_i}\t{lines_i}"
                        )
                    return {
                        "correct_steps": n_correct,
                        "reason": "incorrect edit",
                        "error_details": "\n".join(error_details),
                    }
                n_correct += 1

        return {
            "correct_steps": n_correct,
            "reason": "success",
            "error_details": "",
        }


@weave.op
def run_trials(config: EvalEditMemoryConfig, agent: Agent, name: str, n_trials: int):
    results = []
    for i in range(n_trials):
        start_time = time.time()
        result = eval_edit_memory(config, agent)
        duration = time.time() - start_time
        results.append({**result, "duration": duration})
        print(f"{name} {i}: {result} {duration:.2f}s")

    return {
        "average_correct_steps": sum(result["correct_steps"] for result in results)
        / n_trials,
        "average_duration": sum(result["duration"] for result in results) / n_trials,
        "reason_counts": {
            reason: sum(1 for result in results if result["reason"] == reason)
            for reason in set(res["reason"] for res in results)
        },
    }


if __name__ == "__main__":
    weave.init("programmerdev-eval-fine")
    agent_specs = [
        # (agent, "agent"),
        (agent_replace, "agent_replace"),
    ]
    config = EvalEditMemoryConfig(n_lines=100)
    n_trials = 10
    results = {}
    for agent, name in agent_specs:
        results[name] = run_trials(config, agent, name, n_trials)
    from rich import print

    print(results)