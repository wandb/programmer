import { OpenAI } from "openai";
import {
  ChatCompletion,
  ChatCompletionMessage,
} from "openai/resources/chat/completions";

export interface ActionSpec {
  name: string;
  description: string;
  parameters: Record<string, any>; // JSON Schema
}

export type Action = {
  name: string;
  parameters: Record<string, any>;
};

export type ActionResponse = unknown;

interface Fn<I extends {}, O extends {}> {
  description: string;
  run: (input: I) => Promise<O>;
  // trials: (n: number, input: I) => O[]
  // map: (over: I[]) => O[]
}

interface Observation {}

export interface Environment<O extends Observation> {
  observe: () => O;
  availableActions: () => ActionSpec[];
  act: (actions: Action[]) => ActionResponse[];
}

export type EnvironmentObservationType<E extends Environment<any>> =
  E extends Environment<infer O> ? O : never;

export type ActorResponse = ChatCompletionMessage;

interface Actor<O extends Observation>
  extends Fn<
    { availableActions: ActionSpec[]; observation: O; memory: Memory },
    ActorResponse
  > {
  // description = "Actor"
  run: (input: {
    availableActions: ActionSpec[];
    observation: O;
    memory: Memory;
  }) => Promise<ActorResponse>;
}

type MemoryMessageAgent = ActorResponse;

type MemoryMessageUser = {
  role: "user";
  message: string;
};

type MemoryMessageActionResponse = {
  role: "tool";
  content: string;
  tool_call_id: string;
};

type MemoryMessage =
  | MemoryMessageAgent
  | MemoryMessageUser
  | MemoryMessageActionResponse;

export type Memory = MemoryMessage[];

type ActionWithId = Action & {
  id: string;
};

const memoryAddAgentResponse = (
  memory: Memory,
  response: ActorResponse
): Memory => {
  return [...memory, response];
};

const memoryAddActionResponses = (
  memory: Memory,
  actions: ActionWithId[],
  responses: ActionResponse[]
): Memory => {
  return [
    ...memory,
    ...responses.map((response, index) => ({
      role: "tool" as const,
      tool_call_id: actions[index].id,
      content:
        typeof response === "string" ? response : JSON.stringify(response),
    })),
  ];
};

export class LLM<I extends {}, O extends {}> implements Fn<I, O> {
  description = "LLM";
  model: string;
  temperature: number;
  paramsFn: (input: I) => any;
  responseFn: (input: I, response: ChatCompletion) => O;

  constructor(
    model: string,
    temperature: number,
    paramsFn: (input: I) => any,
    responseFn: (input: I, response: ChatCompletion) => O
  ) {
    this.model = model;
    this.temperature = temperature;
    this.paramsFn = paramsFn;
    this.responseFn = responseFn;
  }

  run: (input: I) => Promise<O> = async (input) => {
    const client = new OpenAI();
    const params = this.paramsFn(input);
    const response = await client.chat.completions.create({
      model: this.model,
      temperature: this.temperature,
      ...params,
    });
    return this.responseFn(input, response);
  };
}

export class Stepper<O extends Observation>
  implements
    Fn<
      { env: Environment<O>; memory: Memory },
      { env: Environment<O>; memory: Memory }
    >
{
  description = "Stepper";
  actor: Actor<O>;

  constructor(actor: Actor<O>) {
    this.actor = actor;
  }

  run: (input: {
    env: Environment<O>;
    memory: Memory;
  }) => Promise<{ env: Environment<O>; memory: Memory }> = async ({
    env,
    memory,
  }) => {
    const availableActions = env.availableActions();
    const observation = env.observe();
    console.log("observation", observation);
    const actorResponse = await this.actor.run({
      availableActions,
      observation,
      memory,
    });
    console.log("actorResponse", JSON.stringify(actorResponse, null, 2));
    memory = memoryAddAgentResponse(memory, actorResponse);

    if (actorResponse.tool_calls) {
      const actions = actorResponse.tool_calls.map((toolCall) => ({
        id: toolCall.id,
        name: toolCall.function.name,
        parameters: JSON.parse(toolCall.function.arguments),
      }));

      const actionResponses = env.act(actions);
      console.log("actionResponses", JSON.stringify(actionResponses, null, 2));

      memory = memoryAddActionResponses(memory, actions, actionResponses);
    }
    return { env, memory };
  };
}

export class SequentialRunner<O extends Observation>
  implements
    Fn<
      { env: Environment<O>; memory: Memory },
      { env: Environment<O>; memory: Memory }
    >
{
  description = "SequentialRunner";
  maxSteps: number;
  stepper: Stepper<O>;
  stopFn: (env: Environment<O>, memory: Memory) => boolean;

  constructor(
    stepper: Stepper<O>,
    maxSteps: number,
    stopFn: (env: Environment<O>, memory: Memory) => boolean
  ) {
    this.stepper = stepper;
    this.maxSteps = maxSteps;
    this.stopFn = stopFn;
  }

  run: (input: {
    env: Environment<O>;
    memory: Memory;
  }) => Promise<{ env: Environment<O>; memory: Memory }> = async ({
    env,
    memory,
  }) => {
    for (let i = 0; i < this.maxSteps; i++) {
      const { env: newEnv, memory: newMemory } = await this.stepper.run({
        env,
        memory,
      });
      env = newEnv;
      memory = newMemory;
      if (this.stopFn(env, memory)) {
        break;
      }
    }
    return { env, memory };
  };
}

async function main() {}

main();
