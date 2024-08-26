SYSTEM_MESSAGE = """Assistant is a programming assistant named "programmer".
programmer is autonomous, and does not stop to ask for user input until it is totally stuck.
programmer always has access to a shell and local filesystem in perform tasks, via its tools.
programmer writes code directly to files instead of to the terminal, unless it is showing snippets for discussion.
"""

from .tools import (
    list_files,
    write_to_file,
    read_from_file,
    run_command,
    view_image,
    read_lines_from_file,
    replace_lines_in_file,
)
from .agent import Agent

agent = Agent(
    model_name="gpt-4o-2024-08-06",
    temperature=0.7,
    system_message=SYSTEM_MESSAGE,
    tools=[list_files, write_to_file, read_from_file, run_command, view_image],
)

agent_claude_replace = Agent(
    model_name="claude-3-5-sonnet-20240620",
    temperature=0.7,
    system_message=SYSTEM_MESSAGE,
    tools=[
        list_files,
        run_command,
        view_image,
        read_lines_from_file,
        replace_lines_in_file,
    ],
)

agent_claude = Agent(
    model_name="claude-3-5-sonnet-20240620",
    temperature=0.7,
    system_message=SYSTEM_MESSAGE,
    tools=[list_files, write_to_file, read_from_file, run_command, view_image],
)

# This still doesn't work as well. gpt-4o will get stuck in loops when it tries to
# do multiple file edits in one call, for example.
agent_replace = Agent(
    model_name="gpt-4o-2024-08-06",
    temperature=0.7,
    system_message=SYSTEM_MESSAGE,
    tools=[
        list_files,
        run_command,
        view_image,
        read_lines_from_file,
        replace_lines_in_file,
    ],
)
