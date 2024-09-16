import {
  Action,
  ActionSpec,
  ActorResponse,
  EnvironmentObservationType,
  LLM,
  SequentialRunner,
  Stepper,
  Memory,
} from "./actor";
import { SimpleTextAdventure } from "./simpleGame";

async function main() {
  const env = new SimpleTextAdventure();
  const actor = new LLM<
    {
      availableActions: ActionSpec[];
      observation: EnvironmentObservationType<SimpleTextAdventure>;
      memory: Memory;
    },
    ActorResponse
  >(
    "gpt-4o",
    0,
    (inputs) => ({
      messages: [
        {
          role: "system",
          content: "You are a player in a simple text adventure game.",
        },
        ...inputs.memory,
        {
          role: "user",
          content: inputs.observation.message,
        },
      ],
      tools: inputs.availableActions.map((actionSpec) => ({
        type: "function",
        function: actionSpec,
      })),
    }),
    (inputs, choice) => {
      return choice.message;
    }
  );
  const stepper = new Stepper(actor);
  const runner = new SequentialRunner(stepper, 10, (env, memory) => {
    const lastMessage = memory[memory.length - 1];
    if (lastMessage.role === "assistant" && lastMessage.tool_calls == null) {
      return true;
    }
    return false;
  });
  const result = await runner.run({ env, memory: [] });
  console.log(result.env.observe());
  // console.log(JSON.stringify(result.memory, null, 2));
}

main().catch(console.error);
