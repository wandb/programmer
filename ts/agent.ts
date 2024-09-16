import { ActionSpec, Observation, Environment } from "./environment";
import {
  Trajectory,
  AgentResponse,
  trajectoryAdd,
  trajectoryAddAgentResponse,
  trajectoryAddActionResponses,
} from "./trajectory";
import { Fn, BaseFn } from "./fn";

interface Agent<O extends Observation>
  extends Fn<
    { availableActions: ActionSpec[]; observation: O; trajectory: Trajectory },
    AgentResponse
  > {
  // description = "Agent"
  run: (input: {
    availableActions: ActionSpec[];
    observation: O;
    trajectory: Trajectory;
  }) => Promise<AgentResponse>;
}

type AgentFn<O extends Observation> = Fn<
  { trajectory: Trajectory; env: Environment<O> },
  { trajectoryDelta: Trajectory; env: Environment<O> }
>;

export class Stepper<O extends Observation>
  extends BaseFn<
    { trajectory: Trajectory; env: Environment<O> },
    { trajectoryDelta: Trajectory; env: Environment<O> }
  >
  implements AgentFn<O>
{
  description = "Stepper";
  agent: Agent<O>;

  constructor(agent: Agent<O>) {
    super("Stepper");
    this.agent = agent;
  }

  async trials(
    n: number,
    input: {
      trajectory: Trajectory;
      env: Environment<O>;
    }
  ): Promise<{ trajectoryDelta: Trajectory; env: Environment<O> }[]> {
    const { trajectory, env } = input;
    const availableActions = env.availableActions();
    const observation = env.observe();
    console.log("observation", observation);
    const agentResponses = await this.agent.trials(n, {
      availableActions,
      observation,
      trajectory,
    });

    return agentResponses.map((agentResponse) => {
      let trajectoryDelta: Trajectory = [agentResponse];

      // clone
      const envState = env.save();
      let newEnv = env.load(envState);

      if (agentResponse.tool_calls) {
        const actions = agentResponse.tool_calls.map((toolCall) => ({
          id: toolCall.id,
          name: toolCall.function.name,
          parameters: JSON.parse(toolCall.function.arguments),
        }));

        const actionResponses = newEnv.act(actions);
        trajectoryDelta = trajectoryAddActionResponses(
          trajectoryDelta,
          actions,
          actionResponses
        );
      }
      return { env: newEnv, trajectoryDelta };
    });
  }

  async run(input: {
    trajectory: Trajectory;
    env: Environment<O>;
  }): Promise<{ trajectoryDelta: Trajectory; env: Environment<O> }> {
    const { trajectory, env } = input;
    const availableActions = env.availableActions();
    const observation = env.observe();
    console.log("observation", observation);
    const agentResponse = await this.agent.run({
      availableActions,
      observation,
      trajectory,
    });
    console.log("agentResponse", JSON.stringify(agentResponse, null, 2));
    let trajectoryDelta: Trajectory = [agentResponse];

    if (agentResponse.tool_calls) {
      const actions = agentResponse.tool_calls.map((toolCall) => ({
        id: toolCall.id,
        name: toolCall.function.name,
        parameters: JSON.parse(toolCall.function.arguments),
      }));

      const actionResponses = env.act(actions);
      console.log("actionResponses", JSON.stringify(actionResponses, null, 2));

      trajectoryDelta = trajectoryAddActionResponses(
        trajectoryDelta,
        actions,
        actionResponses
      );
    }
    return { env, trajectoryDelta };
  }
}

export class SequentialRunner<O extends Observation>
  extends BaseFn<
    { trajectory: Trajectory; env: Environment<O> },
    { trajectoryDelta: Trajectory; env: Environment<O> }
  >
  implements AgentFn<O>
{
  description = "SequentialRunner";
  maxSteps: number;
  stepper: AgentFn<O>;
  stopFn: (trajectory: Trajectory, env: Environment<O>) => boolean;

  constructor(
    stepper: AgentFn<O>,
    maxSteps: number,
    stopFn: (trajectory: Trajectory, env: Environment<O>) => boolean
  ) {
    super("SequentialRunner");
    this.stepper = stepper;
    this.maxSteps = maxSteps;
    this.stopFn = stopFn;
  }

  async trials(
    n: number,
    input: {
      trajectory: Trajectory;
      env: Environment<O>;
    }
  ): Promise<{ trajectoryDelta: Trajectory; env: Environment<O> }[]> {
    return await Promise.all(
      Array.from({ length: n }, async () => {
        const envState = input.env.save();
        const clonedEnv = input.env.load(envState);
        return await this.run({
          trajectory: input.trajectory,
          env: clonedEnv,
        });
      })
    );
  }

  async run(input: {
    trajectory: Trajectory;
    env: Environment<O>;
  }): Promise<{ trajectoryDelta: Trajectory; env: Environment<O> }> {
    let { trajectory, env } = input;
    let trajectoryDelta: Trajectory = [];
    for (let i = 0; i < this.maxSteps; i++) {
      const { trajectoryDelta: newTrajectoryDelta, env: newEnv } =
        await this.stepper.run({
          trajectory,
          env,
        });
      env = newEnv;
      trajectoryDelta = trajectoryAdd(trajectoryDelta, newTrajectoryDelta);
      trajectory = trajectoryAdd(trajectory, newTrajectoryDelta);
      if (this.stopFn(trajectory, env)) {
        break;
      }
    }
    return { trajectoryDelta, env };
  }
}

async function main() {}

main();
