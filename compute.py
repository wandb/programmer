from pydantic import BaseModel
import openai
from typing import Any
from rich import print

# To explore:
# - can run take *args/**kwargs instead of input or no?
# - [x] can we recursively use TrialsComputeFn
# - async / faster
# - weave tracking
# - back tracking agent


class Prompt(BaseModel):
    messages: list[dict]

    def format(self, **kwargs):
        return [
            {
                "role": message["role"],
                "content": message["content"].format(**kwargs),
            }
            for message in self.messages
        ]


class Fn(BaseModel):
    description: str

    def map(self, over):
        return [self.run(item) for item in over]

    def trials(self, n, input):
        return [self.run(input) for _ in range(n)]

    def run(self, input):
        raise NotImplementedError


class OpenAIComputeFn(Fn):
    model: str
    temperature: float
    prompt: Prompt
    response_format: type[BaseModel]

    def trials(self, n, input):
        messages: list[Any] = self.prompt.format(**input)
        response = openai.beta.chat.completions.parse(
            model=self.model,
            temperature=self.temperature,
            messages=messages,
            n=n,
            response_format=self.response_format,
        )
        return [choice.message.parsed for choice in response.choices]

    def run(self, input):
        messages: list[Any] = self.prompt.format(**input)
        response = openai.beta.chat.completions.parse(
            model=self.model,
            temperature=self.temperature,
            messages=messages,
            response_format=self.response_format,
        )
        return response.choices[0].message.parsed


class TrialsComputeFn1(Fn):
    fn: Fn
    score: Fn
    pick: Fn
    n: int

    def run(self, input):
        print("Running trials", input)
        outputs = self.fn.trials(self.n, input)
        print("OUTPUTS", outputs)
        score_inputs = [
            {
                "description": self.fn.description,
                "input": input,
                "output": output.output,
            }
            for output in outputs
        ]
        print("Scoring")
        print("SCORE INPUTS", score_inputs)
        score_outputs = self.score.map(score_inputs)
        print("SCORES", score_outputs)
        pick_inputs = [
            {"output": output, "score": score.output}
            for output, score in zip(outputs, score_outputs)
        ]
        print("PICKING", pick_inputs)
        return self.pick.run(pick_inputs)["output"]


class TrialsComputeFn2(Fn):
    fn: Fn
    pick: Fn
    n: int

    def run(self, input):
        print("Running trials", input)
        outputs = self.fn.trials(self.n, input)
        print("OUTPUTS", outputs)
        pick_inputs = {
            "description": self.fn.description,
            "input": input,
            "outputs": [o.output for o in outputs],
        }
        print("PICKING", pick_inputs)
        pick_output = self.pick.run(pick_inputs)
        print("PICK OUTPUT", pick_output)
        return pick_output


class PickBest(Fn):
    description: str = "pick the best result"

    def run(self, input):
        return max(input, key=lambda x: x["score"])


# OK I need supporting facts to be stated in real terms, not variables. Like this
#                'The GCD of 93 and 36 is 3, satisfying the given condition.',
# 'The LCM of 93 and 36 is 1116, which is 12 times 93, satisfying the condition.',
# '93 + 36 = 129, which is the maximum possible sum.'


class SupportedAnswer(BaseModel):
    final_answer: str
    supporting_facts: list[str]


class ProblemSolverResponse(BaseModel):
    reasoning: str
    output: SupportedAnswer


problem_solver = OpenAIComputeFn(
    model="gpt-4o-2024-08-06",
    temperature=0.7,
    description="solve the problem",
    prompt=Prompt(messages=[{"role": "user", "content": "solve {problem}"}]),
    response_format=ProblemSolverResponse,
)


class ScoreResponse(BaseModel):
    reasoning: str
    output: int


scorer = OpenAIComputeFn(
    model="gpt-4o-2024-08-06",
    temperature=0.7,
    description="score the results of a function call",
    prompt=Prompt(
        messages=[
            {
                "role": "user",
                "content": "a function with description {description} was called with {input} and returned {output}. score the output on a scale of 0 to 5",
            }
        ]
    ),
    response_format=ScoreResponse,
)


class CorrectnessScoreResponse(BaseModel):
    reasoning: str
    output: bool


correctness_scorer = OpenAIComputeFn(
    model="gpt-4o-2024-08-06",
    temperature=0.7,
    description="determine if the results of a function call are correct",
    prompt=Prompt(
        messages=[
            {
                "role": "user",
                "content": "a function with description {description} was called with {input} and returned {output}. Is the function correct? Do not solve the problem yourself. Instead try to prove the function wrong by providing a counterexample.",
            }
        ]
    ),
    response_format=CorrectnessScoreResponse,
)


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


int_sum_problem = "The greatest common divisor of two positive integers less than $100$ is equal to $3$. Their least common multiple is twelve times one of the integers. What is the largest possible sum of the two integers?"


def pick_best_algs():
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

    better_problem_solver = TrialsComputeFn2(
        description="solve the problem",
        fn=problem_solver,
        pick=pick_best,
        n=3,
    )

    better_better_problem_solver = TrialsComputeFn2(
        description="solve the problem",
        fn=better_problem_solver,
        pick=pick_best,
        n=3,
    )

    better_picker = TrialsComputeFn2(
        description="pick the best result",
        fn=pick_best,
        pick=pick_best,
        n=3,
    )
    better_picker_problem_solver = TrialsComputeFn2(
        description="solve the problem",
        fn=problem_solver,
        pick=better_picker,
        n=3,
    )

    print(
        better_picker_problem_solver.run(
            {
                "problem": int_sum_problem,
            }
        )
    )


def decompose():

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

    print(
        planner.run(
            {
                "problem": int_sum_problem,
            }
        )
    )


if __name__ == "__main__":
    decompose()
