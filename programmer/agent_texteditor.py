from typing import Any, Optional, Union
from pydantic import Field
import litellm
import time
from openai.types.chat import (
    ChatCompletionMessageParam,
)

import weave
from weave.trace.vals import WeaveList
from weave.flow.chat_util import OpenAIStream

from .console import Console
from .tool_calling import chat_call_tool_params, perform_tool_calls
from .text_editor import TextEditor, TextEditorState, TextEditorStateful
from .environment import get_current_environment, EnvironmentSnapshotKey
from .agent import AgentState, Agent


# Weave bug workaround: adding two WeaveLists can create that cause
# downstream crashes.
# Can be removed after https://github.com/wandb/weave/pull/2165 is merged.
def weavelist_add(self: Union[list, WeaveList], other: list) -> Union[list, WeaveList]:
    if isinstance(self, list):
        return self + other
    if not isinstance(other, list):
        return NotImplemented
    return WeaveList(list(self) + other, server=self.server)


class AgentStateTextEditor(AgentState):
    text_editor_state: TextEditorState = Field(default_factory=TextEditorState)

    def with_history(self, history: list[Any]) -> "AgentStateTextEditor":
        next_state = super().with_history(history)
        return AgentStateTextEditor(
            history=next_state.history,
            env_snapshot_key=next_state.env_snapshot_key,
            text_editor_state=self.text_editor_state,
        )

    def with_texteditor_state(
        self, text_editor_state: TextEditorState
    ) -> "AgentStateTextEditor":
        return AgentStateTextEditor(
            history=self.history,
            env_snapshot_key=self.env_snapshot_key,
            text_editor_state=text_editor_state,
        )


def unweavify(v: Any) -> Any:
    if isinstance(v, list):
        return [unweavify(m) for m in v]
    elif isinstance(v, dict):
        return {k: unweavify(v) for k, v in v.items()}
    else:
        return v


class AgentTextEditor(Agent):
    text_editor: TextEditor

    def initial_state(self, history: list[Any]) -> AgentStateTextEditor:
        return AgentStateTextEditor(history=history)

    @weave.op()
    def step(self, state: AgentStateTextEditor) -> AgentStateTextEditor:
        """Run a step of the agent.

        Args:
            state: The current state of the environment.
            action: The action to take.

        Returns:
            The new state of the environment.
        """
        Console.step_start("agent", "green")
        # Printing this is ugly
        # ref = weave.obj_ref(state)
        # if ref:
        #     print("state ref:", ref.uri())

        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": self.system_message},
        ]
        open_file_info = state.text_editor_state.get_open_file_info()
        messages.append(
            {
                "role": "system",
                "content": open_file_info.format_for_messages(),
            }
        )

        messages += state.history

        self_tools = [*self.tools] or []

        text_editor_stateful = TextEditorStateful(
            self.text_editor, state.text_editor_state
        )

        # @weave.op
        def open_file(path: str, start_line: int) -> str:
            f"""Open a buffer of {self.text_editor.OPEN_CHUNK_SIZE} lines from the given file.

            Args:
                path: The path to the file.
                start_line: The line number to start reading from (0-indexed).

            Returns:
                "success" if the file was opened successfully,
                "error: <error message>" if the file was not opened successfully.
            """
            response = text_editor_stateful.open_file(path, start_line)
            if response.action_result.success:
                return "success"
            else:
                return f"error: {response.action_result.error}"

        # @weave.op
        def close_file_range(path: str, start_line: int, n_lines: int) -> str:
            """Close a buffer of lines from the given file.

            Args:
                path: The path to the file.
                start_line: The line number to start reading from (0-indexed).
                n_lines: The number of lines to close.

            Returns:
                "success" if the file was closed successfully.
            """
            response = text_editor_stateful.close_file_range(path, start_line, n_lines)
            return "success"

        # @weave.op
        def replace_file_lines(
            path: str, start_line: int, n_lines: int, lines: str
        ) -> str:
            """Replace a buffer of lines in the given file.

            Args:
                path: The path to the file.
                start_line: The line number to start reading from (0-indexed).
                n_lines: The number of lines to replace.
                lines: The lines to replace the existing lines with.

            Returns:
                "success" if the file was replaced successfully,
                "error: <error message>" if the file was not replaced successfully.
            """
            response = self.text_editor.replace_file_lines(
                state.text_editor_state, path, start_line, n_lines, lines
            )
            if response.action_result.success:
                return "success"
            else:
                return f"error: {response.action_result.error}"

        self_tools += [open_file, close_file_range, replace_file_lines]

        # make type checkers happy by passing NotGiven instead of None
        tools = None
        if self_tools:
            tools = chat_call_tool_params(self_tools)

        Console.chat_response_start()

        # Workaround a weave bug, litellm tries to deepcopy messages which has
        # a TraceDict. TraceDict is not pickable, because it has a reference to
        # a weave server, which has a lock.
        messages = unweavify(messages)

        stream = litellm.completion(
            model=self.model_name,
            temperature=self.temperature,
            messages=messages,
            tools=tools,
            stream=True,
            timeout=60,
        )
        wrapped_stream = OpenAIStream(stream)  # type: ignore
        for chunk in wrapped_stream:
            if chunk.choices[0].delta.content:
                Console.chat_message_content_delta(chunk.choices[0].delta.content)

        response = wrapped_stream.final_response()
        response_message = response.choices[0].message
        if response_message.content:
            Console.chat_response_complete(response_message.content)

        new_messages = []
        # we always store the dict representations of messages in agent state
        # instead of mixing in some pydantic objects.
        new_messages.append(response_message.model_dump(exclude_none=True))
        if response_message.tool_calls:
            new_messages.extend(
                perform_tool_calls(self_tools, response_message.tool_calls)
            )
        next_state = state.with_history(new_messages)
        next_state = next_state.with_texteditor_state(text_editor_stateful.state)
        return next_state

    @weave.op()
    def run(self, state: AgentStateTextEditor, max_runtime_seconds: int = -1):
        start_time = time.time()
        while True:
            last_message = state.history[-1]
            if last_message["role"] == "assistant" and "tool_calls" not in last_message:
                return {"state": state, "stop_reason": "done"}
            state = self.step(state)
            if (
                max_runtime_seconds > 0
                and time.time() - start_time > max_runtime_seconds
            ):
                return {"state": state, "stop_reason": "time_limit_exceeded"}
