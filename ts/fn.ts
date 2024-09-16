export interface Fn<I extends {}, O extends {}> {
  description: string;
  run: (input: I) => Promise<O>;
  trials: (n: number, input: I) => Promise<O[]>;
  // map: (over: I[]) => O[]
}

export class BaseFn<I extends {}, O extends {}> implements Fn<I, O> {
  constructor(public description: string) {}

  //   run: (input: I) => Promise<O> = async (input: I) => {
  //     throw new Error("Method not implemented.");
  //   };
  async run(input: I): Promise<O> {
    throw new Error("Method not implemented.");
  }
  async trials(n: number, input: I): Promise<O[]> {
    throw new Error("Method not implemented.");
  }
}
