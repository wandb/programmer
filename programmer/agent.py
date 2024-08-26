from typing import Any, Optional, Union
from pydantic import Field
import litellm
from openai.types.chat import (
    ChatCompletionMessageParam,
)

import weave
from weave.trace.vals import WeaveList
from weave.flow.chat_util import OpenAIStream

from .console import Console
from .tool_calling import chat_call_tool_params, perform_tool_calls
from .environment import get_current_environment, EnvironmentSnapshotKey


def get_commit_message(history: list[Any]) -> str:
    # Commit message is the most recent message with 'content'
    for i in range(len(history) - 1, -1, -1):
        if history[i].get("role") != "tool" and "content" in history[i]:
            return f'{history[i]["role"]}: {history[i]["content"]}'
    return "commit"


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


def unweavify(v: Any) -> Any:
    if isinstance(v, list):
        return [unweavify(m) for m in v]
    elif isinstance(v, dict):
        return {k: unweavify(v) for k, v in v.items()}
    else:
        return v


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
        tools = None
        if self.tools:
            tools = chat_call_tool_params(self.tools)

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
                perform_tool_calls(self.tools, response_message.tool_calls)
            )

        # new_history = state.history + new_messages
        new_history = weavelist_add(state.history, new_messages)
        msg = get_commit_message(new_history)

        environment = get_current_environment()
        snapshot_key = environment.make_snapshot(msg)

        return AgentState(history=new_history, env_snapshot_key=snapshot_key)

    @weave.op()
    def run(self, state: AgentState):
        while True:
            last_message = state.history[-1]
            if last_message["role"] == "assistant" and "tool_calls" not in last_message:
                return state
            state = self.step(state)
