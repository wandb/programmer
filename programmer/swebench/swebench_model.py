import weave

from ..agent import Agent, AgentState, TimeLimitExceeded
from ..tools import RemoteContainerToolContext


class SWEBenchProgrammerModel(weave.Model):
    agent: Agent
    max_runtime_seconds: int = 60

    def predict(self, instance):
        instance_id = instance["instance_id"]
        problem_statement = instance["problem_statement"]
        initial_prompt = f"""You are in a checkout of the a git repo. Please identify and fix the issue described in the problem statement.

<problem_statement>
{problem_statement}
</problem_statement>"""
        state = AgentState(
            history=[
                {
                    "role": "user",
                    "content": initial_prompt,
                },
            ],
        )

        tc = RemoteContainerToolContext(
            "http://localhost:8000",
            "/testbed",
            "source /opt/miniconda3/bin/activate && conda activate testbed && ",
        )
        container_id = f"sweb.eval.x86_64.{instance_id}"
        with tc.context(container_id):
            try:
                self.agent.run(state, max_runtime_seconds=self.max_runtime_seconds)
            except TimeLimitExceeded:
                return {"errorcode": "runtime", "answer": ""}
            answer_result = tc.run_command("git diff")
            answer = answer_result["output"]
        return {"answer": answer}
