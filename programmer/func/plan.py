from pydantic import BaseModel

from .llm import OpenAIComputeFn
from .prompt import Prompt


class PlannerOutput(BaseModel):
    subfunction_declarations: list[str]
    algorithm_steps: list[str]


class PlannerResponse(BaseModel):
    reasoning: str
    output: PlannerOutput


planner = OpenAIComputeFn(
    model="gpt-4o-2024-08-06",
    temperature=0.7,
    description="write an algorithm for how to solve the problem",
    prompt=Prompt(
        messages=[
            {
                "role": "user",
                "content": "write an algorithm for how to solve the problem, in pseudocode. Do not solve the problem. <problem>{problem}</problem>",
            }
        ]
    ),
    response_format=PlannerResponse,
)
