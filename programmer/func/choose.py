from pydantic import BaseModel

from .llm import OpenAIComputeFn
from .prompt import Prompt


class SupportedAnswer(BaseModel):
    final_answer: str
    supporting_facts: list[str]


class PickBestOutputValueCheck(BaseModel):
    output: str
    validation_reasoning: str


class PickBestReasoning(BaseModel):
    output_check_plan: str
    output_value_checks: list[PickBestOutputValueCheck]
    final_reasoning: str


class PickBestResponse(BaseModel):
    reasoning: PickBestReasoning
    output: SupportedAnswer


pick_best = OpenAIComputeFn(
    model="gpt-4o-2024-08-06",
    temperature=0.7,
    description="pick the best result",
    prompt=Prompt(
        messages=[
            {
                "role": "user",
                "content": "a stochastic function with description {description} was called N times with {input} and returned {outputs}. Pick the best output. Validate each unique output step by step and determine whether it is correct v the others.",
            }
        ]
    ),
    response_format=PickBestResponse,
)
