import { ChatCompletionMessage } from "openai/resources/chat/completions";
import { Action, ActionResponse } from "./environment";

export type ActorResponse = ChatCompletionMessage;

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

export const trajectoryAddAgentResponse = (
  trajectory: Trajectory,
  response: ActorResponse
): Trajectory => {
  return [...trajectory, response];
};

export const trajectoryAddActionResponses = (
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
