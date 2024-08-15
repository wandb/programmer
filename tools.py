import base64
import json
import os
import subprocess
import weave

LENGTH_LIMIT = 10000


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
    """Write text to a file at the tiven path.

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
