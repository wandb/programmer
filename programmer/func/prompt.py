from pydantic import BaseModel


class Prompt(BaseModel):
    messages: list[dict]

    def format(self, **kwargs):
        return [
            {
                "role": message["role"],
                "content": message["content"].format(**kwargs),
            }
            for message in self.messages
        ]
