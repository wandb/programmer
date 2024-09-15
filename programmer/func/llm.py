from typing import Any
from pydantic import BaseModel

from .func import Fn
from .prompt import Prompt

import openai


class OpenAIComputeFn(Fn):
    model: str
    temperature: float
    prompt: Prompt
    response_format: type[BaseModel]

    def trials(self, n, input):
        messages: list[Any] = self.prompt.format(**input)
        response = openai.beta.chat.completions.parse(
            model=self.model,
            temperature=self.temperature,
            messages=messages,
            n=n,
            response_format=self.response_format,
        )
        return [choice.message.parsed for choice in response.choices]

    def run(self, input):
        messages: list[Any] = self.prompt.format(**input)
        response = openai.beta.chat.completions.parse(
            model=self.model,
            temperature=self.temperature,
            messages=messages,
            response_format=self.response_format,
        )
        return response.choices[0].message.parsed
