import { Action, Environment, Observation } from "./environment";
import { AgentFn } from "./agent";
import { Trajectory, trajectoryAdd } from "./trajectory";

export class EnvAgent<O extends Observation> implements Environment<string> {
  constructor(
    private agent: AgentFn<O>,
    private env: Environment<O>,
    private trajectory: Trajectory = []
  ) {}

  save = () => {
    throw new Error("Not implemented");
  };
  load = () => {
    throw new Error("Not implemented");
  };
  observe = () => {
    return "";
  };
  availableActions = () => {
    return [
      {
        name: "do_task",
        description: "Do a task",
        parameters: {
          type: "object",
          properties: {
            task: { type: "string" },
          },
          required: ["task"],
        },
      },
    ];
  };

  async act(actions: Action[]): Promise<any> {
    const results: any[] = [];

    for (const action of actions) {
      switch (action.name) {
        case "do_task":
          results.push(await this.actionDoTask(action.parameters.task));
          break;
        default:
          results.push(`Unknown action: ${action.name}`);
      }
    }

    return results;
  }

  async actionDoTask(
    task: string
  ): Promise<{ env: Environment<O>; trajectoryDelta: Trajectory }> {
    const trajectory = trajectoryAdd(this.trajectory, [
      {
        role: "user",
        content: `Perform this task: ${task}`,
      },
    ]);
    const { env, trajectoryDelta } = await this.agent.run({
      trajectory,
      env: this.env,
    });
    this.env = env;
    this.trajectory = trajectoryAdd(trajectory, trajectoryDelta);
    return { env, trajectoryDelta };
  }
}
