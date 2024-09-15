import {
  Action,
  ActionSpec,
  EnvironmentObservationType,
  LLM,
  SequentialRunner,
  Stepper,
} from "./actor";
import { SimpleTextAdventure } from "./simpleGame";

const env = new SimpleTextAdventure();
const actor = new LLM<
  {
    availableActions: ActionSpec[];
    observation: EnvironmentObservationType<SimpleTextAdventure>;
  },
  Action[]
>(
  "gpt-4o",
  0,
  (inputs: {
    availableActions: ActionSpec[];
    observation: EnvironmentObservationType<SimpleTextAdventure>;
  }) => ({
    messages: [
      {
        role: "system",
        content: "You are a player in a simple text adventure game.",
      },
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
  (inputs, response) => {
    const message = response.choices[0].message;
    if (message.tool_calls) {
      return message.tool_calls
        .map((tool_call: any) => {
          const action = inputs.availableActions.find(
            (action) => action.name === tool_call.function.name
          );
          if (action) {
            try {
              const parameters = JSON.parse(tool_call.function.arguments);
              return {
                name: tool_call.function.name,
                parameters: parameters,
              };
            } catch (error) {
              console.error(`Invalid JSON in tool call arguments: ${error}`);
            }
          } else {
            console.error(`Unknown action: ${tool_call.function.name}`);
          }
        })
        .filter((action: any): action is Action => action !== undefined);
    }
    return [];
  }
);

async function main() {
  const stepper = new Stepper(actor);
  const runner = new SequentialRunner(stepper, 3);
  const env2 = await runner.run({ env });
  console.log(env2.observe());
}

main().catch(console.error);
