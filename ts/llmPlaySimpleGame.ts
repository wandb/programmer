import { SequentialRunner, Stepper } from "./agent";
import { LLM, LLMStructuredOutput } from "./llm";
import { Trajectory, AgentResponse } from "./trajectory";
import {
  ActionSpec,
  EnvironmentType,
  EnvironmentObservationType,
} from "./environment";
import { SimpleTextAdventure } from "./simpleGame";
import { BestOfNTrials } from "./strategy";
import { z } from "zod";
import { init } from "weave";

async function main() {
  await init("programmerjs-dev1");

  const env = new SimpleTextAdventure();

  const actor = new LLM(
    "Solve the game",
    "gpt-4o-2024-08-06",
    0.7,
    (inputs: {
      trajectory: Trajectory;
      availableActions: ActionSpec[];
      observation: EnvironmentObservationType<SimpleTextAdventure>;
    }) => ({
      messages: [
        {
          role: "system",
          content:
            "You are a player in a simple text adventure game.\n" +
            "Solve the game without asking for user input.\n" +
            "Summarize what you've learned throughout the gamebefore taking each step.\n",
        },
        ...inputs.trajectory,
        {
          role: "user",
          content: inputs.observation.message,
        },
      ],
      tools: inputs.availableActions.map((actionSpec) => ({
        type: "function",
        function: actionSpec,
      })),
    })
  );

  const chooseFromTrials = new LLMStructuredOutput(
    "Choose the best function output",
    "gpt-4o-2024-08-06",
    0,
    (inputs: { description: string; input: any; outputs: any }) => [
      {
        role: "user",
        content: `
          A stochastic function with the description:

          <description>
          ${inputs.description}
          </description>

          was called N times with the input:
        
          <input>
          ${JSON.stringify(inputs.input, null, 2)}
          </input>

          and returned the following outputs:
          <outputs>
          ${JSON.stringify(inputs.outputs, null, 2)}
          </outputs>

          Pick the best output. Validate each unique output step by step and determine whether it is correct v the others.
          `,
      },
    ],
    z.object({
      reasoning: z.string(),
      choiceId: z.string(),
    })
  );

  const stopFn = (
    trajectory: Trajectory,
    env: EnvironmentType<SimpleTextAdventure>
  ) => {
    if (env.observe().won) {
      return true;
    }
    const lastMessage = trajectory[trajectory.length - 1];
    if (lastMessage.role === "assistant" && lastMessage.tool_calls == null) {
      return true;
    }
    return false;
  };

  // const llmTrials = new BestTrial(actor, pick, 3);

  const stepper = new Stepper(actor);

  // const stepperTrials = new BestTrial(stepper, pick, 3);

  const runner = new SequentialRunner(stepper, 5, stopFn);

  const runnerTrials = new BestOfNTrials(runner, chooseFromTrials, 5);

  const runnerRunner = new SequentialRunner(runnerTrials, 5, stopFn);

  const result = await runnerRunner.run({ trajectory: [], env });

  console.log(result.env.observe());
  console.log(JSON.stringify(result.trajectoryDelta, null, 2));
  // console.log(JSON.stringify(result.trajectory, null, 2));
  console.log(
    "NUMBER OF STEPS",
    result.trajectoryDelta.filter((message) => message.role === "assistant")
      .length
  );
  console.log("WON", result.env.observe().won);
}

main().catch(console.error);
