import { ActionSpec, Observation, Environment } from "./environment";
import {
  Trajectory,
  AgentResponse,
  trajectoryAddAgentResponse,
  trajectoryAddActionResponses,
} from "./trajectory";
import { Fn } from "./fn";

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

export class Stepper<O extends Observation>
  implements
    Fn<
      { env: Environment<O>; trajectory: Trajectory },
      { env: Environment<O>; trajectory: Trajectory }
    >
{
  description = "Stepper";
  agent: Agent<O>;

  constructor(agent: Agent<O>) {
    this.agent = agent;
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
    const agentResponse = await this.agent.run({
      availableActions,
      observation,
      trajectory,
    });
    console.log("agentResponse", JSON.stringify(agentResponse, null, 2));
    trajectory = trajectoryAddAgentResponse(trajectory, agentResponse);

    if (agentResponse.tool_calls) {
      const actions = agentResponse.tool_calls.map((toolCall) => ({
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
