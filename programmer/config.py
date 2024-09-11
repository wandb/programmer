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
    splice_lines_in_file,
)
from .agent import Agent
from .agent_texteditor import AgentTextEditor
from .text_editor import TextEditor

agent_4o_basic = Agent(
    name="gpt-4o-2024-08-06_basic",
    model_name="gpt-4o-2024-08-06",
    temperature=0.7,
    system_message=SYSTEM_MESSAGE,
    tools=[list_files, write_to_file, read_from_file, run_command, view_image],
)

agent_4omini_basic = Agent(
    name="gpt-4o-mini-2024-07-08_basic",
    model_name="gpt-4o-mini-2024-07-18",
    temperature=0.7,
    system_message=SYSTEM_MESSAGE,
    tools=[list_files, write_to_file, read_from_file, run_command, view_image],
)

agent_claude_basic = Agent(
    name="claude-3-5-sonnet-basic",
    model_name="claude-3-5-sonnet-20240620",
    temperature=0.7,
    system_message=SYSTEM_MESSAGE,
    tools=[list_files, write_to_file, read_from_file, run_command, view_image],
)

agent_4o_replace = Agent(
    name="gpt-4o-2024-08-06_replace",
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

agent_claude_replace = Agent(
    name="claude-3-5-sonnet-20240620_replace",
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


agent_4o_splice = Agent(
    name="gpt-4o-2024-08-06_splice",
    model_name="gpt-4o-2024-08-06",
    temperature=0.7,
    system_message=SYSTEM_MESSAGE,
    tools=[
        list_files,
        run_command,
        view_image,
        read_lines_from_file,
        splice_lines_in_file,
    ],
)

agent_claude_splice = Agent(
    name="claude-3-5-sonnet-20240620_splice",
    model_name="claude-3-5-sonnet-20240620",
    temperature=0.7,
    system_message=SYSTEM_MESSAGE,
    tools=[
        list_files,
        run_command,
        view_image,
        read_lines_from_file,
        splice_lines_in_file,
    ],
)

text_editor = TextEditor(max_open_size=15000, open_chunk_size=500)
agent_texteditor_4o_basic = AgentTextEditor(
    name="gpt-4o-2024-08-06_texteditor_basic",
    model_name="gpt-4o-2024-08-06",
    temperature=0.7,
    system_message=SYSTEM_MESSAGE,
    text_editor=text_editor,
    tools=[list_files, run_command, view_image],
)

agent_texteditor_4o_basic_temp0 = AgentTextEditor(
    name="gpt-4o-2024-08-06_texteditor_basic_temp0",
    model_name="gpt-4o-2024-08-06",
    temperature=0.0,
    system_message=SYSTEM_MESSAGE,
    text_editor=text_editor,
    tools=[list_files, run_command, view_image],
)
