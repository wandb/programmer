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

// OK I think we really want trajectory delta, instead of modified trajectory

type AgentFn<O extends Observation> = Fn<
  { env: Environment<O>; trajectory: Trajectory },
  { env: Environment<O>; trajectoryDelta: Trajectory }
>;

export class Stepper<O extends Observation>
  extends BaseFn<
    { env: Environment<O>; trajectory: Trajectory },
    { env: Environment<O>; trajectoryDelta: Trajectory }
  >
  implements AgentFn<O>
{
  description = "Stepper";
  agent: Agent<O>;

  constructor(agent: Agent<O>) {
    super("Stepper");
    this.agent = agent;
  }

  trials: (
    n: number,
    input: {
      env: Environment<O>;
      trajectory: Trajectory;
    }
  ) => Promise<{ env: Environment<O>; trajectoryDelta: Trajectory }[]> = async (
    n,
    { env, trajectory }
  ) => {
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
  };

  run: (input: {
    env: Environment<O>;
    trajectory: Trajectory;
  }) => Promise<{ env: Environment<O>; trajectoryDelta: Trajectory }> = async ({
    env,
    trajectory,
  }) => {
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
  };
}

export class SequentialRunner<O extends Observation>
  extends BaseFn<
    { env: Environment<O>; trajectory: Trajectory },
    { env: Environment<O>; trajectoryDelta: Trajectory }
  >
  implements AgentFn<O>
{
  description = "SequentialRunner";
  maxSteps: number;
  stepper: AgentFn<O>;
  stopFn: (env: Environment<O>, trajectory: Trajectory) => boolean;

  constructor(
    stepper: AgentFn<O>,
    maxSteps: number,
    stopFn: (env: Environment<O>, trajectory: Trajectory) => boolean
  ) {
    super("SequentialRunner");
    this.stepper = stepper;
    this.maxSteps = maxSteps;
    this.stopFn = stopFn;
  }

  run: (input: {
    env: Environment<O>;
    trajectory: Trajectory;
  }) => Promise<{ env: Environment<O>; trajectoryDelta: Trajectory }> = async ({
    env,
    trajectory,
  }) => {
    let trajectoryDelta: Trajectory = [];
    for (let i = 0; i < this.maxSteps; i++) {
      const { env: newEnv, trajectoryDelta: newTrajectoryDelta } =
        await this.stepper.run({
          env,
          trajectory,
        });
      env = newEnv;
      trajectoryDelta = trajectoryAdd(trajectoryDelta, newTrajectoryDelta);
      trajectory = trajectoryAdd(trajectory, newTrajectoryDelta);
      if (this.stopFn(env, trajectory)) {
        break;
      }
    }
    return { env, trajectoryDelta };
  };
}

async function main() {}

main();
