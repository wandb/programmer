from pydantic import BaseModel

from .llm import OpenAIComputeFn
from .prompt import Prompt


class ProblemDecomposition(BaseModel):
    subproblems: list[str]


class ProblemSolverResponse(BaseModel):
    reasoning: str
    output: ProblemDecomposition


problem_decomposer = OpenAIComputeFn(
    model="gpt-4o-2024-08-06",
    temperature=0.7,
    description="decompose the problem into subproblems",
    prompt=Prompt(
        messages=[
            {
                "role": "user",
                "content": "decompose the following problem into subproblems. Do not solve the problem. <problem>{problem}</problem>",
            }
        ]
    ),
    response_format=ProblemSolverResponse,
)
