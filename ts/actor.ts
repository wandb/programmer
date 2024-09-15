import { OpenAI } from "openai";

export interface ActionSpec {
  name: string;
  description: string;
  parameters: Record<string, any>; // JSON Schema
}

export type Action = {
  name: string;
  parameters: Record<string, any>;
};

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
  act: (actions: Action[]) => Environment<O>;
}

export type EnvironmentObservationType<E extends Environment<any>> =
  E extends Environment<infer O> ? O : never;

interface Actor<O extends Observation>
  extends Fn<{ availableActions: ActionSpec[]; observation: O }, Action[]> {
  // description = "Actor"
  run: (input: {
    availableActions: ActionSpec[];
    observation: O;
  }) => Promise<Action[]>;
}

export class LLM<I extends {}, O extends {}> implements Fn<I, O> {
  description = "LLM";
  model: string;
  temperature: number;
  paramsFn: (input: I) => any;
  responseFn: (input: I, response: any) => O;

  constructor(
    model: string,
    temperature: number,
    paramsFn: (input: I) => any,
    responseFn: (input: I, response: any) => O
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
  implements Fn<{ env: Environment<O> }, Environment<O>>
{
  description = "Stepper";
  actor: Actor<O>;

  constructor(actor: Actor<O>) {
    this.actor = actor;
  }

  run: (input: { env: Environment<O> }) => Promise<Environment<O>> = async ({
    env,
  }) => {
    const availableActions = env.availableActions();
    const observation = env.observe();
    console.log("OBSERVATION", observation);
    const actions = await this.actor.run({
      availableActions,
      observation,
    });
    console.log("ACTIONS", actions);
    return env.act(actions);
  };
}

export class SequentialRunner<O extends Observation>
  implements Fn<{ env: Environment<O> }, Environment<O>>
{
  description = "SequentialRunner";
  maxSteps: number;
  stepper: Stepper<O>;

  constructor(stepper: Stepper<O>, maxSteps: number) {
    this.stepper = stepper;
    this.maxSteps = maxSteps;
  }

  run: (input: { env: Environment<O> }) => Promise<Environment<O>> = async ({
    env,
  }) => {
    let current_env = env;
    for (let i = 0; i < this.maxSteps; i++) {
      current_env = await this.stepper.run({ env: current_env });
    }
    return current_env;
  };
}

async function main() {}

main();
