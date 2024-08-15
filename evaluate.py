import asyncio
import json
import weave

from agent import AgentState
from config import agent

# Need to serialize AgentState as json for now since we can't save weave Objects
# in Dataset set.


@weave.op()
def rollout_len(model_output: str):
    final_state = AgentState(**json.loads(model_output))
    return len(final_state.history)


@weave.op()
def final_answer_substr(expected_substr: str, model_output: str):
    final_state = AgentState(**json.loads(model_output))
    final_message = final_state.history[-1]
    return expected_substr in final_message["content"]


eval = weave.Evaluation(
    dataset=[
        {
            "state": AgentState(
                history=[{"role": "user", "content": "what's in frog.jpeg"}]
            ).model_dump_json(),
            "expected_substr": "kitten",
        }
    ],
    scorers=[rollout_len, final_answer_substr],
)

# Can't call a method with evaluation yet, so use this funky bridge function.
# This also does our AgentState deserialization.


@weave.op()
def model_agent_bridge(state: str):
    return agent.run(AgentState(**json.loads(state))).model_dump_json()


if __name__ == "__main__":
    weave.init_local_client()
    result = asyncio.run(eval.evaluate(model_agent_bridge))
