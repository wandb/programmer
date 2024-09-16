import { OpenAI } from "openai";
import { ChatCompletion } from "openai/resources/chat/completions";
import { zodResponseFormat } from "openai/helpers/zod";
import { z } from "zod";

import { Fn, BaseFn } from "./fn";

export class LLM<I extends {}, O extends {}>
  extends BaseFn<I, O>
  implements Fn<I, O>
{
  // description = "LLM";
  model: string;
  temperature: number;
  paramsFn: (input: I) => any;
  responseFn: (input: I, response: ChatCompletion.Choice) => O;

  constructor(
    description: string,
    model: string,
    temperature: number,
    paramsFn: (input: I) => any,
    responseFn: (input: I, response: ChatCompletion.Choice) => O
  ) {
    super(description);
    this.model = model;
    this.temperature = temperature;
    this.paramsFn = paramsFn;
    this.responseFn = responseFn;
  }

  trials: (n: number, input: I) => Promise<O[]> = async (n, input) => {
    const client = new OpenAI();
    const params = this.paramsFn(input);
    const response = await client.chat.completions.create({
      model: this.model,
      temperature: this.temperature,
      n,
      ...params,
    });
    return response.choices.map((choice) => this.responseFn(input, choice));
  };

  run: (input: I) => Promise<O> = async (input) => {
    const client = new OpenAI();
    const params = this.paramsFn(input);
    const response = await client.chat.completions.create({
      model: this.model,
      temperature: this.temperature,
      ...params,
    });
    return this.responseFn(input, response.choices[0]);
  };
}

export class LLMStructuredOutput<
    Z extends z.ZodObject<any>,
    I extends {},
    O extends z.infer<Z>
  >
  extends BaseFn<I, O>
  implements Fn<I, O>
{
  model: string;
  temperature: number;
  responseFormat: Z;
  messagesFn: (input: I) => any[];

  constructor(
    description: string,
    model: string,
    temperature: number,
    messagesFn: (input: I) => any,
    responseFormat: Z
  ) {
    super(description);
    this.model = model;
    this.temperature = temperature;
    this.messagesFn = messagesFn;
    this.responseFormat = responseFormat;
  }

  trials: (n: number, input: I) => Promise<O[]> = async (n, input) => {
    const client = new OpenAI();
    const messages = this.messagesFn(input);
    const response = await client.beta.chat.completions.parse({
      model: this.model,
      temperature: this.temperature,
      n,
      messages,
      response_format: zodResponseFormat(this.responseFormat, "result"),
    });
    return response.choices.map((choice) => choice.message.parsed as any);
  };

  run: (input: I) => Promise<O> = async (input) => {
    const client = new OpenAI();
    const messages = this.messagesFn(input);
    const response = await client.beta.chat.completions.parse({
      model: this.model,
      temperature: this.temperature,
      messages,
      response_format: zodResponseFormat(this.responseFormat, "result"),
    });
    return response.choices[0].message.parsed as any;
  };
}
