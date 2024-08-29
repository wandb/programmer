import tempfile
import os
import time
import concurrent.futures
from typing import TypedDict, Callable
from contextlib import contextmanager

import weave
from weave.trace import call_context

from ..agent import AgentState, Agent
from ..config import agent, agent_replace, agent_splice
from ..tools import tool_context, LocalToolContext

# NOTES
# - Try with other LLM and tool configs now that I have this test


# @pytest.fixture
@contextmanager
def tempdir():
    with tempfile.TemporaryDirectory() as dir_:
        with tool_context(LocalToolContext(dir_)) as tc:
            yield tc


def call_descendent_error_count(call):
    has_error = int(call.exception is not None)
    descendent_errors = sum(call_descendent_error_count(c) for c in call._children)
    return has_error + descendent_errors


class EvalEditMemoryConfig(TypedDict):
    n_lines: int
    run_timeout_seconds: int


@weave.op
def eval_edit_memory(config: EvalEditMemoryConfig, agent: Agent):
    with tempdir() as ctx:
        lines = []
        n_alpha = 10
        num_per_alpha = config["n_lines"] // n_alpha
        for attempt in range(config["n_lines"]):
            lines.append(
                f"{chr(65 + attempt // num_per_alpha)}{attempt % num_per_alpha}"
            )

        with open(ctx.resolve_path("file.txt"), "w") as f:
            prev_file_contents = "\n".join(lines)
            f.write(prev_file_contents)

        task_correct = False
        state = AgentState()

        def step6_insert_ampersands(lines):
            new_lines = []
            for l in lines:
                if l.endswith("***"):
                    new_lines.append("&&")
                new_lines.append(l)
            return new_lines

        results: dict = {"task_info": []}
        for task_idx, (prompt, modify_expected_fn) in enumerate(
            [
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
                (
                    "Add a line '😊😊😊' to the start of the file.",
                    lambda lines: ["😊😊😊"] + lines,
                ),
                (
                    "Add a line '😔😔😔' to the end of the file.",
                    lambda lines: lines + ["😔😔😔"],
                ),
                (
                    "Replace the Z lines we added earlier with a single blank line.",
                    lambda lines: lines[: lines.index("Z")]
                    + [""]
                    + lines[lines.index("ZZZ") + 1 :],
                ),
                (
                    "Append *** to the end of each line that ends with 7.",
                    lambda lines: [l + "***" if l.endswith("7") else l for l in lines],
                ),
                (
                    "Insert '&&' before each of the '***' lines we just added.",
                    step6_insert_ampersands,
                ),
            ]
        ):
            print(f"*** TASK: {task_idx}, {prompt}")
            state = AgentState(
                history=state.history
                + [
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
            )
            lines = modify_expected_fn(lines)
            task_info = {"task_idx": task_idx, "attempts": []}
            task_correct = False
            results["task_info"].append(task_info)
            for attempt in range(5):
                attempt_info: dict = {"attempt_idx": attempt}
                task_info["attempts"].append(attempt_info)

                run_result, call = agent.run.call(
                    agent, state, max_runtime_seconds=config["run_timeout_seconds"]
                )
                if call.exception is not None:
                    print("*** EXCEPTION ***")
                    print(call.exception)
                    attempt_info["stop_reason"] = "exception"
                    continue
                attempt_info["stop_reason"] = run_result["stop_reason"]
                stop_reason = run_result["stop_reason"]
                if stop_reason == "time_limit_exceeded":
                    print("*** TIME LIMIT EXCEEDED ***")

                next_state = run_result["state"]

                attempt_info["n_messages"] = len(next_state.history) - len(
                    state.history
                )
                attempt_info["n_errors"] = call_descendent_error_count(call)
                state = next_state

                with open(ctx.resolve_path("file.txt"), "r") as f:
                    file_contents = f.read().strip()
                attempt_info["made_edit"] = file_contents != prev_file_contents
                prev_file_contents = file_contents

                file_lines = file_contents.split("\n")
                attempt_correct = file_contents == "\n".join(lines)
                attempt_info["correct"] = attempt_correct
                if attempt_correct:
                    task_correct = True
                    # stop attempts
                    break

                attempt_info["error_details"] = mismatch_details(lines, file_lines)

                print()
                print(f"*** FAILED ATTEMPT Task: {task_idx} Attempt: {attempt}")
                print()
                state = AgentState(
                    history=state.history
                    + [
                        {
                            "role": "user",
                            "content": "edit was incorrect, try again",
                        },
                    ],
                )
            task_info["correct"] = task_correct
            task_info["n_errors"] = sum(
                attempt_info["n_errors"] for attempt_info in task_info["attempts"]
            )
            task_info["n_messages"] = sum(
                attempt_info["n_messages"] for attempt_info in task_info["attempts"]
            )
            if not task_correct:
                # Don't do further tasks.
                break

        results["success"] = task_correct
        results["completed_tasks"] = sum(
            task_info["correct"] for task_info in results["task_info"]
        )
        results["total_errors"] = sum(
            task_info["n_errors"] for task_info in results["task_info"]
        )
        return results


def mismatch_details(lines, file_lines):
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
        error_details.append(f"{line_correct_str} {file_lines_i}\t{lines_i}")

    return "\n".join(error_details)


@weave.op
def run_trials(
    config: EvalEditMemoryConfig,
    agent: Agent,
    name: str,
    n_trials: int,
    max_workers: int = 16,
):
    current_call = call_context.get_current_call()
    if current_call is None:
        raise Exception("Should not happen, no current call")

    def run_single_trial():
        with call_context.current_call(current_call):
            start_time = time.time()
            result = eval_edit_memory(config, agent)
            duration = time.time() - start_time
            print(f"{name}: {result} {duration:.2f}s")
            return {**result, "duration": duration}

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(run_single_trial) for _ in range(n_trials)]
        results = [
            future.result() for future in concurrent.futures.as_completed(futures)
        ]

    return {
        "success": sum(result["success"] for result in results) / n_trials,
        "avg_errors": sum(result["total_errors"] for result in results) / n_trials,
        "avg_completed_tasks": sum(result["completed_tasks"] for result in results)
        / n_trials,
    }


if __name__ == "__main__":
    weave.init("programmerdev-eval-fine")
    agent_specs = [
        (agent, "agent"),
        # (agent_claude, "agent_claude"),
        # (agent_claude_replace, "agent_claude_replace"),
        (agent_replace, "agent_replace"),
        (agent_splice, "agent_splice"),
    ]
    config = EvalEditMemoryConfig(n_lines=100, run_timeout_seconds=60)
    n_trials = 5
    results = {}
    for agent, name in agent_specs:
        results[name] = run_trials(config, agent, name, n_trials, max_workers=5)
    from rich import print

    print(results)
