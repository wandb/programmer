import { OpenAI } from "openai";
import { ChatCompletionMessage } from "openai/resources/chat/completions";
import { zodResponseFormat } from "openai/helpers/zod";
import { z } from "zod";

import { Fn, BaseFn } from "./fn";

export class LLM<I extends {}> extends BaseFn<I, ChatCompletionMessage> {
  model: string;
  temperature: number;
  paramsFn: (input: I) => any;

  constructor(
    description: string,
    model: string,
    temperature: number,
    paramsFn: (input: I) => any
  ) {
    super(description);
    this.model = model;
    this.temperature = temperature;
    this.paramsFn = paramsFn;
  }

  trials: (n: number, input: I) => Promise<ChatCompletionMessage[]> = async (
    n,
    input
  ) => {
    const client = new OpenAI();
    const params = this.paramsFn(input);
    const response = await client.chat.completions.create({
      model: this.model,
      temperature: this.temperature,
      n,
      ...params,
    });
    return response.choices.map((choice) => choice.message);
  };

  run: (input: I) => Promise<ChatCompletionMessage> = async (input) => {
    const client = new OpenAI();
    const params = this.paramsFn(input);
    const response = await client.chat.completions.create({
      model: this.model,
      temperature: this.temperature,
      ...params,
    });
    return response.choices[0].message;
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
