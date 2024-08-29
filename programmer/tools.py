import base64
import json
import os
import subprocess
import weave
import contextlib
import shlex
from contextvars import ContextVar
from contextlib import contextmanager
from typing import Protocol, Union, TypedDict, Optional
import requests

LENGTH_LIMIT = 30000

# TODO:
# - get rid of resolve_path
# - must return FileNotFoundError in read_file in Remote


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


@contextlib.contextmanager
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


def read_image_as_base64(path: str):
    ext = os.path.splitext(path)[1]
    if ext not in [".jpg", ".jpeg", ".png"]:
        raise ValueError("Only .jpg, .jpeg, and .png files are supported.")
    if ext in [".jpg", ".jpeg"]:
        mime_type = "image/jpeg"
    else:
        mime_type = "image/png"
    # Read the image file in binary mode
    with open(path, "rb") as image_file:
        # Encode the image to base64
        base64_bytes = base64.b64encode(image_file.read())
        # Convert the base64 bytes to string
        base64_string = base64_bytes.decode("utf-8")
        # Format the string as required
        formatted_base64_string = f"data:{mime_type};base64,{base64_string}"
        return formatted_base64_string


@weave.op()
def view_image(path: str):
    """View a png or jpg image file.

    Args:
        path: The path to the image file.

    Returns:
        A message indicating that the image was displayed successfully.
    """
    context = get_current_context()
    full_path = context.resolve_path(path)
    base64_image = read_image_as_base64(full_path)

    return f"Image {full_path} displayed in next message.", {
        "role": "user",
        "content": [
            {
                "type": "image_url",
                "image_url": {"url": base64_image, "detail": "high"},
            },
        ],
    }


@weave.op()
def list_files(directory: str) -> str:
    """List names of all files in a directory.

    Args:
        directory: The directory to list.

    Returns:
        The list of files in the directory.
    """
    context = get_current_context()
    # full_path = context.resolve_path(directory)
    result = context.run_command(f"ls {directory}")
    exit_code = result["exit_code"]
    output = result["output"]
    if exit_code != 0:
        raise Exception(f"Failed to list files: {output}")
    if output == "":
        return "[No files found]"
    if len(output) > LENGTH_LIMIT:
        output = output[:LENGTH_LIMIT]
        output += "\n... (truncated)"
    return output


@weave.op()
def write_to_file(path: str, content: str) -> str:
    """Write text to a file at the given path.

    Args:
        path: The path to the file.
        content: The content to write to the file.

    Returns:
        A message indicating whether the file was written successfully.
    """
    context = get_current_context()
    if len(content) > LENGTH_LIMIT:
        content = content[:LENGTH_LIMIT]
        content += "\n... (truncated)"
    context.write_file(path, content)
    return "File written successfully."


@weave.op
def read_from_file(path: str) -> str:
    """Read text from a file at the given path.

    Args:
        path: The path to the file.

    Returns:
        The content of the file.
    """
    context = get_current_context()
    result = context.read_file(path)
    if len(result) > LENGTH_LIMIT:
        result = result[:LENGTH_LIMIT]
        result += "\n... (truncated)"
    return result


@weave.op()
def run_command(command: str) -> str:
    """Run a shell command and return its output.

    Args:
        command: The command to run.

    Returns:
        The output of the command.
    """
    context = get_current_context()
    result = context.run_command(command)

    exit_code = result["exit_code"]
    output = result["output"]

    if len(output) > LENGTH_LIMIT:
        output = output[:LENGTH_LIMIT]
        output += "\n... (truncated)"

    result = f"Exit code: {exit_code}\n"
    if output:
        result += f"OUTPUT\n{output}\n"
    return result


@weave.op
def read_lines_from_file(file_path: str, start_line: int) -> str:
    """Read up to 500 lines from a file starting at a specific line number.

    Args:
        file_path: The path to the file.
        start_line: The line number to start reading from (1-indexed).

    Returns:
        A string with each line prefixed by its line number.

    Raises:
        Exception: If the file does not exist or start_line is invalid.
    """
    context = get_current_context()
    full_path = context.resolve_path(file_path)
    content = context.read_file(full_path)
    lines = content.splitlines()

    if start_line < 1 or start_line > len(lines):
        raise Exception("Invalid start_line number.")

    end_line = min(start_line + 500, len(lines) + 1)
    result = ""

    for i in range(start_line - 1, end_line - 1):
        result += f"{i + 1}:{lines[i]}\n"

    return result


@weave.op
def replace_lines_in_file(
    file_path: str,
    start_line: int,
    remove_line_count: int,
    previous_lines: str,
    new_lines: str,
) -> str:
    """Replace lines in a file from start_line to end_line with new_lines. Changes are committed to the file.

    Args:
        file_path: The path to the file.
        start_line: The starting line number for replacement (1-indexed).
        remove_line_count: The number of lines to remove, starting with start_line.
        previous_lines: The previous lines to replace, as a single string. This must match the existing lines, or an exception is raised.
        new_lines: The new lines to insert, as a single string.

    Returns:
        Success message, otherwise raises an exception.

    Raises:
        Exception: If the line range is invalid or file cannot be accessed.
    """
    context = get_current_context()
    full_path = context.resolve_path(file_path)
    try:
        content = context.read_file(full_path)
    except FileNotFoundError:
        content = ""
    lines = content.splitlines()

    end_line = start_line + remove_line_count

    if start_line < 1 or end_line < start_line or start_line > len(lines) + 1:
        raise Exception("Invalid line range.")

    prev_line_split = previous_lines.splitlines()
    if not lines[start_line - 1 : end_line - 1] == prev_line_split:
        raise Exception("Previous lines do not match.")

    # Adjust end_line if it exceeds the current number of lines
    end_line = min(end_line, len(lines) + 1)

    # Convert new_lines string into a list of lines
    new_lines_list = new_lines.splitlines()

    # Replace the specified line range
    lines[start_line - 1 : end_line - 1] = new_lines_list

    # Write the modified lines back to the file
    context.write_file(full_path, "\n".join(lines) + "\n")

    # Determine the range for the output with a 5-line buffer
    output_start = max(start_line - 6, 0)
    output_end = min(start_line - 1 + len(new_lines_list) + 6, len(lines))
    result = ""

    for i in range(output_start, output_end):
        result += f"{i + 1}:{lines[i]}\n"

    return result


@weave.op
def splice_lines_in_file(
    file_path: str,
    start_line: int,
    remove_line_count: int,
    previous_lines: str,
    new_lines: str,
) -> str:
    """Remove remove_line_count lines, starting with start_line, then insert new_lines so that first line is inserted at index start_line.

    To append, use last line index + 1.

    Args:
        file_path: The path to the file.
        start_line: The starting line number for replacement (1-indexed).
        remove_line_count: The number of lines to remove, starting with start_line.
        previous_lines: The previous lines to replace, as a single string. This must match the existing lines, or an exception is raised.
        new_lines: The new lines to insert, as a single string. The first line inserted will be at index start_line.

    Returns:
        Success message, otherwise raises an exception.

    Raises:
        Exception: If the line range is invalid or file cannot be accessed.
    """
    context = get_current_context()
    full_path = context.resolve_path(file_path)
    try:
        content = context.read_file(full_path)
    except FileNotFoundError:
        content = ""
    lines = content.splitlines()

    end_line = start_line + remove_line_count

    if start_line < 1 or end_line < start_line or start_line > len(lines) + 1:
        raise Exception("Invalid line range.")

    prev_line_split = previous_lines.splitlines()
    if not lines[start_line - 1 : end_line - 1] == prev_line_split:
        raise Exception("Previous lines do not match.")

    # Adjust end_line if it exceeds the current number of lines
    end_line = min(end_line, len(lines) + 1)

    # Convert new_lines string into a list of lines
    new_lines_list = new_lines.splitlines()

    # Replace the specified line range
    lines[start_line - 1 : end_line - 1] = new_lines_list

    # Write the modified lines back to the file
    context.write_file(full_path, "\n".join(lines) + "\n")

    # Determine the range for the output with a 5-line buffer
    output_start = max(start_line - 6, 0)
    output_end = min(start_line - 1 + len(new_lines_list) + 6, len(lines))
    result = ""

    for i in range(output_start, output_end):
        result += f"{i + 1}:{lines[i]}\n"

    return result
