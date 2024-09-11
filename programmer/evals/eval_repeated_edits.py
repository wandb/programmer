import tempfile
import os
import time
import concurrent.futures
from typing import TypedDict, Callable
from contextlib import contextmanager

import weave
from weave.trace import call_context

from ..agent import AgentState, Agent
from ..config import *
from ..io_context import LocalIOContext, io_context, get_io_context

# NOTES
# - Try with other LLM and tool configs now that I have this test


# @pytest.fixture
@contextmanager
def tempdir():
    with tempfile.TemporaryDirectory() as dir_:
        with io_context(LocalIOContext(dir_)) as tc:
            yield tc


def call_descendent_error_count(call):
    has_error = int(call.exception is not None)
    descendent_errors = sum(call_descendent_error_count(c) for c in call._children)
    return has_error + descendent_errors


class EvalEditMemoryConfig(TypedDict):
    n_lines: int
    run_timeout_seconds: int


@weave.op
def eval_edit_memory(
    config: EvalEditMemoryConfig, agent: Agent, name: str, trial_idx: int
):
    call = weave.get_current_call()
    if call:
        call.set_display_name(f"{name}: Trial{trial_idx}")
    with tempdir() as ctx:
        expected_lines = []
        n_alpha = 10
        num_per_alpha = config["n_lines"] // n_alpha
        for attempt in range(config["n_lines"]):
            expected_lines.append(
                f"{chr(65 + attempt // num_per_alpha)}{attempt % num_per_alpha}"
            )

        with open(ctx.resolve_path("file.txt"), "w") as f:
            prev_file_contents = "\n".join(expected_lines)
            f.write(prev_file_contents)

        task_correct = False
        state = agent.initial_state(history=[])

        def step6_insert_ampersands(lines):
            new_lines = []
            for l in lines:
                if l.endswith("***"):
                    new_lines.append("&&")
                new_lines.append(l)
            return new_lines

        results: dict = {}
        task_infos = []
        for task_idx, (task_name, prompt, modify_expected_fn) in enumerate(
            [
                (
                    "replace_range",
                    "file.txt contains lines like 'C4', 'D8' etc. Replace lines 'A7' through 'B4' (inclusive) with 'X\\nY\\n'.",
                    lambda lines: lines[: lines.index("A7")]
                    + ["X", "Y"]
                    + lines[lines.index("B4") + 1 :],
                ),
                (
                    "correct_range",
                    "Actually that edit was wrong. Replace them with 'Z\nZZ\nZZZ\n' instead.",
                    lambda lines: lines[: lines.index("X")]
                    + ["Z", "ZZ", "ZZZ"]
                    + lines[lines.index("Y") + 1 :],
                ),
                (
                    "insert_beginning",
                    "Add a line '😊😊😊' to the start of the file.",
                    lambda lines: ["😊😊😊"] + lines,
                ),
                (
                    "append_end",
                    "Add a line '😔😔😔' to the end of the file.",
                    lambda lines: lines + ["😔😔😔"],
                ),
                (
                    "replace_prior_range",
                    "Replace the Z lines we added earlier with a single blank line.",
                    lambda lines: lines[: lines.index("Z")]
                    + [""]
                    + lines[lines.index("ZZZ") + 1 :],
                ),
                (
                    "distribute_asterisks",
                    "Append *** to the end of each line that ends with 7.",
                    lambda lines: [l + "***" if l.endswith("7") else l for l in lines],
                ),
                (
                    "distribute_ampersand_prefix",
                    "Insert a line containing '&&' prior to each of the '***' lines we just added.",
                    step6_insert_ampersands,
                ),
            ]
        ):
            expected_lines = modify_expected_fn(expected_lines)
            run_task_result = run_task(
                config,
                agent,
                state,
                expected_lines,
                task_idx,
                task_name,
                prompt,
            )
            state = run_task_result["state"]
            task_info = run_task_result["task_info"]
            task_infos.append(task_info)
            task_correct = task_info["correct"]
            if not task_correct:
                # Don't do further tasks.
                break

        results["success"] = task_correct
        results["completed_tasks"] = sum(
            task_info["correct"] for task_info in task_infos
        )
        results["max_attempts"] = max(
            task_info["n_attempts"] for task_info in task_infos
        )
        results["total_errors"] = sum(task_info["n_errors"] for task_info in task_infos)
        return results


@weave.op
def run_task(
    config: EvalEditMemoryConfig,
    agent: Agent,
    state: AgentState,
    expected_lines: list[str],
    task_idx: int,
    task_name: str,
    prompt: str,
):
    call = weave.get_current_call()
    if call:
        call.set_display_name(f"Task{task_idx}: {task_name}")
    print(f"*** TASK: {task_idx}, {prompt}")
    state = state.with_history(
        state.history
        + [
            {
                "role": "user",
                "content": prompt,
            },
        ],
    )
    task_info = {"task_idx": task_idx}
    task_correct = False
    attempts = []
    for attempt_idx in range(2):
        attempt_result = run_attempt(config, agent, state, expected_lines, attempt_idx)
        attempt_info = attempt_result["attempt_info"]
        state = attempt_result["state"]
        if attempt_info["correct"]:
            task_correct = True
            break

        attempts.append(attempt_info)

        print()
        print(f"*** FAILED ATTEMPT Task: {task_idx} Attempt: {attempt_idx}")
        print()
        state = state.with_history(
            state.history
            + [
                {
                    "role": "user",
                    "content": "edit was incorrect, try again",
                },
            ],
        )
    task_info["correct"] = task_correct
    task_info["n_attempts"] = len(attempts)
    task_info["n_errors"] = sum(attempt_info["n_errors"] for attempt_info in attempts)
    task_info["n_messages"] = sum(
        attempt_info["n_messages"] for attempt_info in attempts
    )

    return {
        "task_info": task_info,
        "state": state,
    }


@weave.op
def run_attempt(
    config: EvalEditMemoryConfig,
    agent: Agent,
    state: AgentState,
    expected_lines: list[str],
    attempt_idx: int,
):
    call = weave.get_current_call()
    if call:
        call.set_display_name(f"Attempt{attempt_idx}")
    ctx = get_io_context()
    attempt_info: dict = {
        "attempt_idx": attempt_idx,
        "correct": False,
        "n_errors": 0,
        "n_messages": 0,
    }
    with open(ctx.resolve_path("file.txt"), "r") as f:
        prev_file_contents = f.read().strip()

    run_result, call = agent.run.call(
        agent, state, max_runtime_seconds=config["run_timeout_seconds"]
    )
    attempt_info["n_errors"] = call_descendent_error_count(call)
    if call.exception is not None:
        print("*** EXCEPTION ***")
        print(call.exception)
        attempt_info["stop_reason"] = "exception"
        return {
            "attempt_info": attempt_info,
            "state": state,
        }
    attempt_info["stop_reason"] = run_result["stop_reason"]
    stop_reason = run_result["stop_reason"]
    if stop_reason == "time_limit_exceeded":
        print("*** TIME LIMIT EXCEEDED ***")

    next_state = run_result["state"]

    attempt_info["n_messages"] = len(next_state.history) - len(state.history)
    state = next_state

    with open(ctx.resolve_path("file.txt"), "r") as f:
        file_contents = f.read().strip()
    attempt_info["made_edit"] = file_contents != prev_file_contents

    file_lines = file_contents.split("\n")
    attempt_correct = file_contents == "\n".join(expected_lines)
    attempt_info["correct"] = attempt_correct
    attempt_info["error_details"] = mismatch_details(expected_lines, file_lines)

    return {
        "attempt_info": attempt_info,
        "state": state,
    }


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
    call = weave.get_current_call()
    if call:
        call.set_display_name(name + f"_{n_trials}trials")
    current_call = call_context.get_current_call()
    if current_call is None:
        raise Exception("Should not happen, no current call")

    def run_single_trial(trial_idx: int):
        with call_context.current_call(current_call):
            start_time = time.time()
            result = eval_edit_memory(config, agent, name, trial_idx)
            duration = time.time() - start_time
            print(f"{name}: {result} {duration:.2f}s")
            return {**result, "duration": duration}

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(run_single_trial, trial_idx)
            for trial_idx in range(n_trials)
        ]
        results = [
            future.result() for future in concurrent.futures.as_completed(futures)
        ]

    return {
        "success": sum(result["success"] for result in results) / n_trials,
        "avg_errors": sum(result["total_errors"] for result in results) / n_trials,
        "avg_completed_tasks": sum(result["completed_tasks"] for result in results)
        / n_trials,
        "max_attempts": max(result["max_attempts"] for result in results),
    }


if __name__ == "__main__":
    weave.init("programmerdev-eval-edits1")
    agents = [
        # agent_4omini_basic,
        # agent_4o_basic,
        # agent_claude_basic,
        # agent_4o_replace,
        # agent_claude_replace,
        # agent_4o_splice,
        # agent_claude_splice,
        agent_texteditor_4o_basic,
        agent_texteditor_4o_basic_temp0,
    ]

    config = EvalEditMemoryConfig(n_lines=100, run_timeout_seconds=60)
    n_trials = 50
    config_s = f'{config["n_lines"]}lines_{config["run_timeout_seconds"]}timeout'
    results = {}
    for agent in agents:
        run_name = f"{agent.name}_{config_s}"
        results[agent.name] = run_trials(
            config, agent, run_name, n_trials, max_workers=5
        )
    from rich import print

    print(results)
