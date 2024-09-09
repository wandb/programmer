from typing import Protocol, TypedDict
import os
import subprocess
import requests
import shlex
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Optional, Union


class RunCommandResult(TypedDict):
    exit_code: int
    output: str


class ToolContext(Protocol):
    def write_file(self, path: str, content: str) -> None: ...

    def read_file(self, path: str) -> str: ...

    def run_command(self, command: str) -> RunCommandResult: ...

    def resolve_path(self, path: str) -> str: ...


class LocalToolContext(ToolContext):
    def __init__(self, directory):
        self.directory = os.path.abspath(directory)

    def write_file(self, path: str, content: str) -> None:
        full_path = self.resolve_path(path)
        with open(full_path, "w") as f:
            f.write(content)

    def read_file(self, path: str) -> str:
        full_path = self.resolve_path(path)
        with open(full_path, "r") as f:
            return f.read()

    def run_command(self, command: str) -> RunCommandResult:
        completed_process = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            shell=True,
            cwd=self.directory,
        )
        exit_code = completed_process.returncode
        output = completed_process.stdout.strip()

        return {
            "exit_code": exit_code,
            "output": output,
        }

    def resolve_path(self, path: str) -> str:
        return os.path.join(self.directory, path)


class RemoteContainerToolContext(ToolContext):
    def __init__(self, base_url: str, directory: str, command_prefix: str):
        self.base_url = base_url
        self.container_id = None
        self.directory = directory
        self.command_prefix = command_prefix

    @contextmanager
    def context(self, image_id: str):
        self.start_container(image_id)
        try:
            with tool_context(self):
                yield
        finally:
            self.stop_container()

    def start_container(self, image_id):
        response = requests.post(
            f"{self.base_url}/container/start", json={"image_id": image_id}
        )
        if response.status_code == 200:
            self.container_id = response.json().get("container_id")
        else:
            print(f"Failed to start container: {response.text}")

    def stop_container(self):
        response = requests.post(
            f"{self.base_url}/container/stop",
            json={"container_id": self.container_id, "delete": True},
        )
        if response.status_code == 200:
            self.container_id = None
        else:
            print(f"Failed to stop container: {response.text}")

    def write_file(self, path: str, content: str) -> None:
        full_path = os.path.join(self.directory, path)
        response = requests.post(
            f"{self.base_url}/container/write_file",
            json={
                "container_id": self.container_id,
                "file_path": full_path,
                "file_content": content,
            },
        )
        if response.status_code != 200:
            raise Exception(f"Failed to write file: {response.text}")

    def read_file(self, path: str) -> str:
        full_path = os.path.join(self.directory, path)
        response = requests.post(
            f"{self.base_url}/container/read_file",
            json={"container_id": self.container_id, "file_path": full_path},
        )
        if response.status_code == 200:
            return response.json().get("file_content")
        else:
            raise Exception(f"Failed to read file: {response.text}")

    def run_command(self, command: str) -> RunCommandResult:
        command = self.command_prefix + command
        command = f"bash -c {shlex.quote(command)}"
        response = requests.post(
            f"{self.base_url}/container/run",
            json={
                "container_id": self.container_id,
                "workdir": self.directory,
                "command": command,
            },
        )
        if response.status_code == 200:
            json = response.json()
            return {
                "exit_code": json["exit_code"],
                "output": json["output"],
            }
        else:
            raise Exception(f"Failed to run command: {response.text}")

    def resolve_path(self, path: str) -> str:
        return path  # For remote containers, we assume paths are already resolved


# Create a ContextVar to store the current ToolContext
current_context: ContextVar[
    Optional[Union[LocalToolContext, RemoteContainerToolContext]]
] = ContextVar("current_context", default=None)


@contextmanager
def tool_context(context: Union[LocalToolContext, RemoteContainerToolContext]):
    token = current_context.set(context)
    try:
        yield context
    finally:
        current_context.reset(token)


def get_current_context() -> Union[LocalToolContext, RemoteContainerToolContext]:
    context = current_context.get()
    if context is None:
        return LocalToolContext(".")
    return context
