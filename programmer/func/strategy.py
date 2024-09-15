from typing import Any
from .func import Fn
from .prompt import Prompt


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
