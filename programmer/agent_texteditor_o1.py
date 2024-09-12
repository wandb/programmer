from typing import Any, Union
from dataclasses import dataclass
from pydantic import Field
import openai
from openai.types.chat import ChatCompletionMessageParam
import json
import re
import time
import uuid
from openai.types.chat import (
    ChatCompletionMessageToolCall,
)

import weave
from weave.trace.vals import WeaveList

from .console import Console
from .tool_calling import (
    chat_call_tool_params,
    perform_tool_calls,
    generate_json_schema,
)
from .text_editor import (
    TextEditor,
    TextEditorState,
    TextEditorStateful,
    open_file,
    replace_file_lines,
    text_editor,
)
from .agent import AgentState, Agent


def weavelist_add(self: Union[list, WeaveList], other: list) -> Union[list, WeaveList]:
    if isinstance(self, list):
        return self + other
    if not isinstance(other, list):
        return NotImplemented
    return WeaveList(list(self) + other, server=self.server)


@dataclass
class ToolCallFunction:
    name: str
    arguments: str


@dataclass
class ToolCall:
    function: ToolCallFunction
    id: str


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


class AgentTextEditorO1(Agent):
    parallel_tool_calls: bool = True
    text_editor: TextEditor

    def initial_state(self, history: list[Any]) -> AgentStateTextEditor:
        return AgentStateTextEditor(history=history)

    @weave.op()
    def step(self, state: AgentStateTextEditor) -> AgentStateTextEditor:
        """Run a step of the agent.

        Args:
            state: The current state of the environment.

        Returns:
            The new state of the environment.
        """
        Console.step_start("agent", "green")

        # Prepare messages
        messages: list[ChatCompletionMessageParam] = []

        # Combine system message and open_file_info into a user message
        open_file_info = state.text_editor_state.get_open_file_info()
        initial_content = (
            f"{self.system_message}\n\n{open_file_info.format_for_messages()}"
        )

        # Include descriptions of available tools
        self_tools = [*self.tools] or []
        text_editor_stateful = TextEditorStateful(
            self.text_editor, state.text_editor_state
        )

        self_tools += [open_file, replace_file_lines]

        # Generate tool descriptions
        tools_descriptions = ""
        for tool in self_tools:
            tool_schema = generate_json_schema(tool)
            tool_name = tool.__name__
            tool_description = tool_schema.get("function", {}).get("description", "")
            tool_parameters = tool_schema.get("function", {}).get("parameters", {})
            tools_descriptions += f"\n- {tool_name}: {tool_description}\nParameters: {json.dumps(tool_parameters)}\n"

        initial_content += f"\n\nAvailable tools:{tools_descriptions}\n"

        # Add instructions to the assistant about how to call tools
        initial_content += (
            "When you want to use a tool, please output the tool call in the following format:\n"
            "<tool_call id='unique_id'><tool_name>(<json_arguments>)</tool_call>\n"
            'For example: <tool_call id=\'123\'><open_file>({"file_name": "example.txt"})</open_file></tool_call>\n'
            "Please include the tool call in your response where appropriate."
            "If you have achieved your goal, our you're stuck, don't call a tool!"
        )

        # Add the initial user message
        messages.append(
            {
                "role": "user",
                "content": f"<user_instructions>{initial_content}</user_instructions>",
            }
        )

        # Add conversation history, ensuring only 'assistant' and 'user' roles
        messages += [
            msg for msg in state.history if msg.get("role") in ["assistant", "user"]
        ]

        Console.chat_response_start()

        # Call the OpenAI API
        response = openai.chat.completions.create(
            model=self.model_name,
            temperature=self.temperature,
            messages=messages,
            timeout=600,
        )

        # Get the assistant's response
        response_message = response.choices[0].message

        if response_message.content:
            print(response_message.content)
            Console.chat_response_complete(response_message.content)

        new_messages = []
        # Store the assistant's response
        new_messages.append(
            {
                "role": response_message.role,
                "content": response_message.content,
            }
        )

        # Parse any tool calls from the assistant's response
        tool_calls = self.parse_tool_calls(response_message.content or "")

        if tool_calls:
            with text_editor(text_editor_stateful):
                tool_messages = perform_tool_calls(self_tools, tool_calls)

                # Combine tool call responses into a single user message
                tool_responses = "<tool_call_responses>\n"
                for msg in tool_messages:
                    tool_responses += f"<tool_call_response id='{msg['tool_call_id']}'>{msg['content']}</tool_call_response>\n"
                tool_responses += "</tool_call_responses>"

                new_messages.append({"role": "user", "content": tool_responses})

        new_history = weavelist_add(state.history, new_messages)

        next_state = state.with_history(new_history)
        next_state = next_state.with_texteditor_state(text_editor_stateful.state)
        return next_state

    def parse_tool_calls(self, content: str) -> list:
        tool_calls = []
        pattern = r"<tool_call id='(.*?)'><(.*?)>\((.*?)\)</\2></tool_call>"
        matches = re.finditer(pattern, content, re.DOTALL)
        for match in matches:
            tool_id = match.group(1)
            tool_name = match.group(2)
            arguments = match.group(3)
            tool_call = ToolCall(
                function=ToolCallFunction(
                    name=tool_name,
                    arguments=arguments,
                ),
                id=tool_id,
            )
            tool_calls.append(tool_call)
        return tool_calls

    @weave.op()
    def run(self, state: AgentState, max_runtime_seconds: int = -1):
        start_time = time.time()
        while True:
            last_message = state.history[-1]
            if last_message["role"] == "assistant":
                # Check if there are no tool calls in the content
                if not self.parse_tool_calls(last_message.get("content", "")):
                    return {"state": state, "stop_reason": "done"}
            state = self.step(state)
            if (
                max_runtime_seconds > 0
                and time.time() - start_time > max_runtime_seconds
            ):
                return {"state": state, "stop_reason": "time_limit_exceeded"}
