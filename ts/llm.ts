import { OpenAI } from "openai";
import { wrapOpenAI } from "weave";
import { ChatCompletionMessage } from "openai/resources/chat/completions";
import { zodResponseFormat } from "openai/helpers/zod";
import { z } from "zod";

import { Fn, BaseFn } from "./fn";

// Add these interfaces
interface ToolCallFunction {
  name: string;
  arguments: string;
}

interface ToolCall {
  function: ToolCallFunction;
  id: string;
}

// Add this function
export function parseToolCalls(content: string): ToolCall[] {
  const toolCalls: ToolCall[] = [];
  const pattern = /<tool_call id='(.*?)' name='(.*?)'>(.*?)<\/tool_call>/gs;
  const matches = content.matchAll(pattern);

  for (const match of matches) {
    const toolId = match[1];
    const toolName = match[2];
    const args = match[3];

    const toolCall: ToolCall = {
      function: {
        name: toolName,
        arguments: args,
      },
      id: toolId,
    };

    toolCalls.push(toolCall);
  }

  return toolCalls;
}

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

  async trials(n: number, input: I): Promise<ChatCompletionMessage[]> {
    const client = wrapOpenAI();
    const params = this.paramsFn(input);
    const response = await client.chat.completions.create({
      model: this.model,
      temperature: this.temperature,
      n,
      ...params,
    });
    return response.choices.map((choice) => choice.message);
  }

  async run(input: I): Promise<ChatCompletionMessage> {
    const client = wrapOpenAI();
    const params = this.paramsFn(input);
    const response = await client.chat.completions.create({
      model: this.model,
      temperature: this.temperature,
      ...params,
    });
    return response.choices[0].message;
  }
}

export class LLMBasicMessages<I extends {}> extends LLM<I> {
  constructor(
    description: string,
    model: string,
    temperature: number,
    paramsFn: (input: I) => any
  ) {
    super(description, model, temperature, paramsFn);
  }
  async run(input: I): Promise<ChatCompletionMessage> {
    const client = wrapOpenAI();
    const params = this.paramsFn(input);
    const messages = params.messages.map((message: any) => {
      if (message.role === "system") {
        return {
          role: "user",
          content: `These instructions are important than all others ${message.content}`,
        };
      } else if (message.role === "tool") {
        return {
          role: "user",
          content: `Tool call response for call ${message.tool_call_id}: ${message.content}`,
        };
      } else {
        return message;
      }
    });
    if (params.tools) {
      let tools_message = `Available tools: ${JSON.stringify(
        params.tools
      )}\n\n`;
      tools_message +=
        "When you want to use a tool, please output the tool call in the following format:\n";
      tools_message +=
        "<tool_call id='unique_id' name='tool_name'>...JSON ARGUMENTS...</tool_call>\n";
      tools_message +=
        "For example: <tool_call id='123' name='open_file'>{\"file_name\": \"example.txt\"}</tool_call>\n";
      tools_message +=
        "Please include the tool call in your response where appropriate.\n";

      messages.push({ role: "user", content: tools_message });
    }
    const response = await client.chat.completions.create({
      model: this.model,
      temperature: this.temperature,
      messages,
    });
    const responseMessage = response.choices[0].message;

    // Parse tool calls from the response content
    if (responseMessage.content) {
      const toolCalls = parseToolCalls(responseMessage.content);
      if (toolCalls.length > 0) {
        responseMessage.tool_calls = toolCalls.map((toolCall) => ({
          type: "function",
          id: toolCall.id,
          function: toolCall.function,
        }));
      }
    }

    return responseMessage;
  }
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

  async trials(n: number, input: I): Promise<O[]> {
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
  }

  async run(input: I): Promise<O> {
    const client = wrapOpenAI();
    const messages = this.messagesFn(input);
    const response = await client.beta.chat.completions.parse({
      model: this.model,
      temperature: this.temperature,
      messages,
      response_format: zodResponseFormat(this.responseFormat, "result"),
    });
    return response.choices[0].message.parsed as any;
  }
}
