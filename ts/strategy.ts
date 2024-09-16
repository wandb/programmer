import { BaseFn, Fn } from "./fn";

export class BestTrial<I extends {}, O extends {}> extends BaseFn<I, O> {
  constructor(
    public fn: Fn<I, O>,
    public pick: Fn<
      { description: string; input: I; outputs: { id: string; output: O }[] },
      { choiceId: string }
    >,
    public n: number
  ) {
    super(fn.description);
  }

  async run(input: I): Promise<O> {
    const outputs = await this.fn.trials(this.n, input);
    const outputsWithIds = outputs.map((output, index) => ({
      id: index.toString(),
      output: output,
    }));
    const pickInputs = {
      description: this.fn.description,
      input: input,
      outputs: outputsWithIds,
    };
    const bestOutputId = await this.pick.run(pickInputs);
    console.log("bestOutputId", bestOutputId);
    let bestOutput = outputsWithIds.find(
      (output) => output.id === bestOutputId.choiceId
    );
    if (bestOutput == null) {
      throw new Error("Best output not found");
    }
    return bestOutput.output;
  }
}
