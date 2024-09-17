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

export interface Observation {}

export interface Environment<O extends Observation> {
  observe: () => O;
  availableActions: () => ActionSpec[];
  act: (actions: Action[]) => Promise<ActionResponse[]>;
  save: () => any;
  load: (state: any) => Environment<O>;
}

export type EnvironmentObservationType<E extends Environment<any>> =
  E extends Environment<infer O> ? O : never;

export type EnvironmentType<E extends Environment<any>> = E extends Environment<
  infer O
>
  ? Environment<O>
  : never;
