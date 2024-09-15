from pydantic import BaseModel


class Fn(BaseModel):
    description: str

    def map(self, over):
        return [self.run(item) for item in over]

    def trials(self, n, input):
        return [self.run(input) for _ in range(n)]

    def run(self, input):
        raise NotImplementedError
