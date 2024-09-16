export interface Fn<I extends {}, O extends {}> {
  description: string;
  run: (input: I) => Promise<O>;
  trials: (n: number, input: I) => Promise<O[]>;
  // map: (over: I[]) => O[]
}
