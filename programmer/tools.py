import base64
import json
import os
import subprocess
import weave

LENGTH_LIMIT = 30000


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
    # Run this to make sure it doesn't raise
    base64_image = read_image_as_base64(path)

    return f"Image {path} displayed in next message.", {
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
    result = json.dumps(os.listdir(directory))
    if len(result) > LENGTH_LIMIT:
        result = result[:LENGTH_LIMIT]
        result += "\n... (truncated)"
    return result


@weave.op()
def write_to_file(path: str, content: str) -> str:
    """Write text to a file at the given path.

    Args:
        path: The path to the file.
        content: The content to write to the file.

    Returns:
        A message indicating whether the file was written successfully.
    """
    with open(path, "w") as f:
        f.write(content)
    return "File written successfully."


@weave.op()
def read_from_file(path: str) -> str:
    """Read text from a file at the given path.

    Args:
        path: The path to the file.

    Returns:
        The content of the file.
    """
    with open(path, "r") as f:
        result = f.read()
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
    completed_process = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        shell=True,
    )
    exit_code = completed_process.returncode
    stdout = completed_process.stdout.strip()
    stderr = completed_process.stderr.strip()

    if len(stdout) > LENGTH_LIMIT:
        stdout = stdout[:LENGTH_LIMIT]
        stdout += "\n... (truncated)"
    if len(stderr) > LENGTH_LIMIT:
        stderr = stderr[:LENGTH_LIMIT]
        stderr += "\n... (truncated)"

    result = f"Exit code: {exit_code}\n"
    if stderr:
        result += f"STDERR\n{stderr}\n"
    if stdout:
        result += f"STDOUT\n{stdout}\n"
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
    if not os.path.exists(file_path):
        raise Exception(f"File '{file_path}' does not exist.")

    with open(file_path, "r") as file:
        lines = file.readlines()

    if start_line < 1 or start_line > len(lines):
        raise Exception("Invalid start_line number.")

    end_line = min(start_line + 500, len(lines) + 1)
    result = ""

    for i in range(start_line - 1, end_line - 1):
        result += f"{i + 1}:{lines[i]}"

    return result


@weave.op
def replace_lines_in_file(
    file_path: str, start_line: int, end_line: int, previous_lines: str, new_lines: str
) -> str:
    """Replace lines in a file from start_line to end_line with new_lines. Changes are committed to the file.

    Args:
        file_path: The path to the file.
        start_line: The starting line number for replacement (1-indexed).
        end_line: The ending line number for replacement (exclusive, 1-indexed).
        previous_lines: The previous lines to replace, as a single string. This must match the existing lines, or an exception is raised.
        new_lines: The new lines to insert, as a single string.

    Returns:
        Success message, otherwise raises an exception.

    Raises:
        Exception: If the line range is invalid or file cannot be accessed.
    """
    lines = []
    if os.path.exists(file_path):
        with open(file_path, "r") as file:
            lines = file.readlines()

    if start_line < 1 or end_line < start_line or start_line > len(lines) + 1:
        raise Exception("Invalid line range.")

    prev_line_split = [l + "\n" for l in previous_lines.splitlines()]
    if not lines[start_line - 1 : end_line - 1] == prev_line_split:
        raise Exception("Previous lines do not match.")

    # Adjust end_line if it exceeds the current number of lines
    end_line = min(end_line, len(lines) + 1)

    if not new_lines.endswith("\n"):
        new_lines += "\n"

    # Convert new_lines string into a list of lines
    new_lines_list = new_lines.splitlines(keepends=True)

    # Replace the specified line range
    lines[start_line - 1 : end_line - 1] = new_lines_list

    # Write the modified lines back to the file
    with open(file_path, "w") as file:
        file.writelines(lines)

    # Determine the range for the output with a 5-line buffer
    output_start = max(start_line - 6, 0)
    output_end = min(
        start_line - 1 + len(new_lines_list) + 6, len(lines)
    )  # Calculate buffer correctly
    result = ""

    for i in range(output_start, output_end):
        result += f"{i + 1}:{lines[i]}"

    return result
