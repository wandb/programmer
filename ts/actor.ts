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
  trials: (n: number, input: I) => Promise<O[]>;
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
    { availableActions: ActionSpec[]; observation: O; trajectory: Trajectory },
    ActorResponse
  > {
  // description = "Actor"
  run: (input: {
    availableActions: ActionSpec[];
    observation: O;
    trajectory: Trajectory;
  }) => Promise<ActorResponse>;
}

type TrajectoryMessageAgent = ActorResponse;

type TrajectoryMessageUser = {
  role: "user";
  message: string;
};

type TrajectoryMessageActionResponse = {
  role: "tool";
  content: string;
  tool_call_id: string;
};

type TrajectoryMessage =
  | TrajectoryMessageAgent
  | TrajectoryMessageUser
  | TrajectoryMessageActionResponse;

export type Trajectory = TrajectoryMessage[];

type ActionWithId = Action & {
  id: string;
};

const trajectoryAddAgentResponse = (
  trajectory: Trajectory,
  response: ActorResponse
): Trajectory => {
  return [...trajectory, response];
};

const trajectoryAddActionResponses = (
  trajectory: Trajectory,
  actions: ActionWithId[],
  responses: ActionResponse[]
): Trajectory => {
  return [
    ...trajectory,
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
  responseFn: (input: I, response: ChatCompletion.Choice) => O;

  constructor(
    model: string,
    temperature: number,
    paramsFn: (input: I) => any,
    responseFn: (input: I, response: ChatCompletion.Choice) => O
  ) {
    this.model = model;
    this.temperature = temperature;
    this.paramsFn = paramsFn;
    this.responseFn = responseFn;
  }

  trials: (n: number, input: I) => Promise<O[]> = async (n, input) => {
    const client = new OpenAI();
    const params = this.paramsFn(input);
    const response = await client.chat.completions.create({
      model: this.model,
      temperature: this.temperature,
      n,
      ...params,
    });
    return response.choices.map((choice) => this.responseFn(input, choice));
  };

  run: (input: I) => Promise<O> = async (input) => {
    const client = new OpenAI();
    const params = this.paramsFn(input);
    const response = await client.chat.completions.create({
      model: this.model,
      temperature: this.temperature,
      ...params,
    });
    return this.responseFn(input, response.choices[0]);
  };
}

export class Stepper<O extends Observation>
  implements
    Fn<
      { env: Environment<O>; trajectory: Trajectory },
      { env: Environment<O>; trajectory: Trajectory }
    >
{
  description = "Stepper";
  actor: Actor<O>;

  constructor(actor: Actor<O>) {
    this.actor = actor;
  }

  trials: (
    n: number,
    input: {
      env: Environment<O>;
      trajectory: Trajectory;
    }
  ) => Promise<{ env: Environment<O>; trajectory: Trajectory }[]> = async (
    n,
    input
  ) => {
    const results = [];
    for (let i = 0; i < n; i++) {
      const result = await this.run(input);
      results.push(result);
    }
    return results;
  };

  run: (input: {
    env: Environment<O>;
    trajectory: Trajectory;
  }) => Promise<{ env: Environment<O>; trajectory: Trajectory }> = async ({
    env,
    trajectory,
  }) => {
    const availableActions = env.availableActions();
    const observation = env.observe();
    console.log("observation", observation);
    const actorResponse = await this.actor.run({
      availableActions,
      observation,
      trajectory,
    });
    console.log("actorResponse", JSON.stringify(actorResponse, null, 2));
    trajectory = trajectoryAddAgentResponse(trajectory, actorResponse);

    if (actorResponse.tool_calls) {
      const actions = actorResponse.tool_calls.map((toolCall) => ({
        id: toolCall.id,
        name: toolCall.function.name,
        parameters: JSON.parse(toolCall.function.arguments),
      }));

      const actionResponses = env.act(actions);
      console.log("actionResponses", JSON.stringify(actionResponses, null, 2));

      trajectory = trajectoryAddActionResponses(
        trajectory,
        actions,
        actionResponses
      );
    }
    return { env, trajectory };
  };
}

export class SequentialRunner<O extends Observation>
  implements
    Fn<
      { env: Environment<O>; trajectory: Trajectory },
      { env: Environment<O>; trajectory: Trajectory }
    >
{
  description = "SequentialRunner";
  maxSteps: number;
  stepper: Stepper<O>;
  stopFn: (env: Environment<O>, trajectory: Trajectory) => boolean;

  constructor(
    stepper: Stepper<O>,
    maxSteps: number,
    stopFn: (env: Environment<O>, trajectory: Trajectory) => boolean
  ) {
    this.stepper = stepper;
    this.maxSteps = maxSteps;
    this.stopFn = stopFn;
  }

  trials: (
    n: number,
    input: {
      env: Environment<O>;
      trajectory: Trajectory;
    }
  ) => Promise<{ env: Environment<O>; trajectory: Trajectory }[]> = async (
    n,
    input
  ) => {
    const results = [];
    for (let i = 0; i < n; i++) {
      const result = await this.run(input);
      results.push(result);
    }
    return results;
  };

  run: (input: {
    env: Environment<O>;
    trajectory: Trajectory;
  }) => Promise<{ env: Environment<O>; trajectory: Trajectory }> = async ({
    env,
    trajectory,
  }) => {
    for (let i = 0; i < this.maxSteps; i++) {
      const { env: newEnv, trajectory: newTrajectory } = await this.stepper.run(
        {
          env,
          trajectory,
        }
      );
      env = newEnv;
      trajectory = newTrajectory;
      if (this.stopFn(env, trajectory)) {
        break;
      }
    }
    return { env, trajectory };
  };
}

async function main() {}

main();
