from typing import Any, Optional, Union
from pydantic import Field
from openai import OpenAI
from openai._types import NotGiven
from openai.types.chat import (
    ChatCompletionMessageParam,
)

import weave
from weave.trace.vals import WeaveList
from weave.flow.chat_util import OpenAIStream

from .console import Console
from .tool_calling import chat_call_tool_params, perform_tool_calls
from .environment import get_current_environment, EnvironmentSnapshotKey


def get_last_assistant_content(history: list[Any]) -> Optional[str]:
    for i in range(len(history) - 1, -1, -1):
        if history[i]["role"] == "assistant" and "content" in history[i]:
            return history[i]["content"]
        elif history[i]["role"] == "user":
            break
    return None


# Weave bug workaround: adding two WeaveLists can create that cause
# downstream crashes.
# Can be removed after https://github.com/wandb/weave/pull/2165 is merged.
def weavelist_add(self: Union[list, WeaveList], other: list) -> Union[list, WeaveList]:
    if isinstance(self, list):
        return self + other
    if not isinstance(other, list):
        return NotImplemented
    return WeaveList(list(self) + other, server=self.server)


class AgentState(weave.Object):
    # The chat message history.
    history: list[Any] = Field(default_factory=list)
    env_snapshot_key: Optional[EnvironmentSnapshotKey] = None


class Agent(weave.Object):
    model_name: str
    temperature: float
    system_message: str
    tools: list[Any] = Field(default_factory=list)

    @weave.op()
    def step(self, state: AgentState) -> AgentState:
        """Run a step of the agent.

        Args:
            state: The current state of the environment.
            action: The action to take.

        Returns:
            The new state of the environment.
        """
        Console.step_start("agent", "green")
        ref = weave.obj_ref(state)
        if ref:
            print("state ref:", ref.uri())

        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": self.system_message},
        ]
        messages += state.history

        # make type checkers happy by passing NotGiven instead of None
        tools = NotGiven()
        if self.tools:
            tools = chat_call_tool_params(self.tools)

        Console.chat_response_start()

        client = OpenAI()
        stream = client.chat.completions.create(
            model=self.model_name,
            temperature=self.temperature,
            messages=messages,
            tools=tools,
            stream=True,
            timeout=60,
        )
        wrapped_stream = OpenAIStream(stream)
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
                perform_tool_calls(self.tools, response_message.tool_calls)
            )

        # new_history = state.history + new_messages
        new_history = weavelist_add(state.history, new_messages)
        last_assistant_message = get_last_assistant_content(new_history)
        if last_assistant_message:
            message = last_assistant_message
        else:
            message = "commit"

        environment = get_current_environment()
        snapshot_key = environment.make_snapshot(message)

        return AgentState(history=new_history, env_snapshot_key=snapshot_key)

    @weave.op()
    def run(self, state: AgentState):
        while True:
            last_message = state.history[-1]
            if last_message["role"] == "assistant" and "tool_calls" not in last_message:
                return state
            state = self.step(state)
