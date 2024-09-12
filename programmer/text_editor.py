from typing import Optional, Generic, TypeVar
from dataclasses import dataclass, field
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Optional, TypedDict

import weave

from .io_context import get_io_context


@dataclass(frozen=True)
class LineRange:
    start_line: int
    n_lines: int


@dataclass(frozen=True)
class OpenFileState:
    # Invariant: ranges must be non-overlapping and non-adjacent
    #     and must be in sorted order
    ranges: tuple[LineRange, ...] = field(default_factory=tuple)

    def add_range(self, range: LineRange) -> "OpenFileState":
        # Create a new list of ranges
        new_ranges = list(self.ranges)

        # Find the correct position to insert the new range
        insert_index = 0
        for i, existing_range in enumerate(new_ranges):
            if range.start_line < existing_range.start_line:
                insert_index = i
                break
            insert_index = i + 1

        # Insert the new range
        new_ranges.insert(insert_index, range)

        # Merge overlapping or adjacent ranges
        i = 0
        while i < len(new_ranges) - 1:
            current_range = new_ranges[i]
            next_range = new_ranges[i + 1]

            if (
                current_range.start_line + current_range.n_lines
                >= next_range.start_line
            ):
                # Merge the ranges
                merged_end = max(
                    current_range.start_line + current_range.n_lines,
                    next_range.start_line + next_range.n_lines,
                )
                new_ranges[i] = LineRange(
                    current_range.start_line, merged_end - current_range.start_line
                )
                new_ranges.pop(i + 1)
            else:
                i += 1

        # Return a new OpenFileState with the updated ranges
        return OpenFileState(ranges=tuple(new_ranges))

    def subtract_range(self, range: LineRange) -> "OpenFileState":
        new_ranges = []
        for existing_range in self.ranges:
            if range.start_line >= existing_range.start_line + existing_range.n_lines:
                # The subtracted range is after this range, keep it as is
                new_ranges.append(existing_range)
            elif range.start_line + range.n_lines <= existing_range.start_line:
                # The subtracted range is before this range, keep it as is
                new_ranges.append(existing_range)
            else:
                # The ranges overlap, we need to split or adjust
                if range.start_line > existing_range.start_line:
                    # Keep the part before the subtracted range
                    new_ranges.append(
                        LineRange(
                            existing_range.start_line,
                            range.start_line - existing_range.start_line,
                        )
                    )
                if (
                    range.start_line + range.n_lines
                    < existing_range.start_line + existing_range.n_lines
                ):
                    # Keep the part after the subtracted range
                    new_ranges.append(
                        LineRange(
                            range.start_line + range.n_lines,
                            (existing_range.start_line + existing_range.n_lines)
                            - (range.start_line + range.n_lines),
                        )
                    )

        return OpenFileState(ranges=tuple(new_ranges))

    def total_lines(self) -> int:
        return sum(r.n_lines for r in self.ranges)

    def is_range_open(self, start_line: int, n_lines: int) -> bool:
        end_line = start_line + n_lines
        for range in self.ranges:
            if (
                range.start_line <= start_line
                and range.start_line + range.n_lines >= end_line
            ):
                return True
        return False


@dataclass(frozen=True)
class TextEditorState:
    open_files: dict[str, OpenFileState] = field(default_factory=dict)

    def total_lines(self) -> int:
        return sum(file.total_lines() for file in self.open_files.values())

    def get_open_file_info(self) -> "OpenFileInfoResult":
        file_io_context = get_io_context()
        open_file_buffers = {}
        for path, open_file in self.open_files.items():
            contents = file_io_context.read_file(path)
            lines = contents.split("\n")
            buffers = []
            for range in open_file.ranges:
                buffer = Buffer(
                    line_range=range,
                    lines=lines[
                        range.start_line - 1 : range.start_line - 1 + range.n_lines
                    ],
                )
                buffers.append(buffer)
            open_file_info = OpenFileInfo(
                buffers=tuple(buffers), total_lines=len(lines)
            )
            open_file_buffers[path] = open_file_info
        return OpenFileInfoResult(open_file_buffers=open_file_buffers)


@dataclass(frozen=True)
class Buffer:
    line_range: LineRange
    lines: list[str]


@dataclass(frozen=True)
class OpenFileInfo:
    buffers: tuple[Buffer, ...] = field(default_factory=tuple)
    total_lines: int = 0

    def n_lines(self) -> int:
        return sum(buffer.line_range.n_lines for buffer in self.buffers)


@dataclass(frozen=True)
class OpenFileInfoResult:
    open_file_buffers: dict[str, OpenFileInfo] = field(default_factory=dict)

    def format_for_messages(self) -> str:
        lines = [
            "Visible file buffers. These are the latest states of any previously opened file ranges, and reflect the results of all prior edits."
        ]
        for path, open_file_info in self.open_file_buffers.items():
            lines.append(f"<file {path}>")
            # lines.append(f"<file_info total_lines={open_file_info.total_lines} />")
            for buffer in open_file_info.buffers:
                lines.append("<buffer>")
                for i, line in enumerate(buffer.lines):
                    lines.append(f"{buffer.line_range.start_line + i}: {line}")
                lines.append("</buffer>")
            lines.append("</file>")
        return "\n".join(lines)


@dataclass(frozen=True)
class ClosedFileRange:
    path: str
    start_line: int
    n_lines: int


@dataclass(frozen=True)
class OpenFileResult:
    success: bool
    error: str


@dataclass(frozen=True)
class WriteFileResult:
    success: bool
    error: str


T = TypeVar("T")


@dataclass(frozen=True)
class TextEditorMutationResult(Generic[T]):
    new_state: TextEditorState
    action_result: T


class LineRangeReplacement(TypedDict):
    start_line: int
    n_lines: int
    lines: str


class TextEditor:
    def __init__(
        self,
        max_open_size: int = 1500,
        open_chunk_size: int = 500,
    ):
        self.MAX_OPEN_SIZE = max_open_size
        self.OPEN_CHUNK_SIZE = open_chunk_size

    def open_file(
        self, state: TextEditorState, path: str, start_line: int
    ) -> TextEditorMutationResult[OpenFileResult]:
        file_io_context = get_io_context()
        try:
            file_contents = file_io_context.read_file(path)
        except FileNotFoundError:
            return TextEditorMutationResult(
                new_state=state,
                action_result=OpenFileResult(success=False, error="File not found"),
            )

        file_lines = file_contents.split("\n")
        file_lines_count = len(file_lines)

        if start_line < 1:
            return TextEditorMutationResult(
                new_state=state,
                action_result=OpenFileResult(
                    success=False,
                    error=f"Start line {start_line} is before the start of the file.",
                ),
            )

        if start_line - 1 >= file_lines_count:
            return TextEditorMutationResult(
                new_state=state,
                action_result=OpenFileResult(
                    success=False,
                    error=f"Start line {start_line} is beyond the end of the file (which has {file_lines_count} lines).",
                ),
            )

        orig_open_file_state = state.open_files.get(path, OpenFileState())
        new_buffer = LineRange(
            start_line, min(self.OPEN_CHUNK_SIZE, file_lines_count - start_line)
        )
        new_open_file_state = orig_open_file_state.add_range(new_buffer)
        added_lines = (
            new_open_file_state.total_lines() - orig_open_file_state.total_lines()
        )

        if state.total_lines() + added_lines > self.MAX_OPEN_SIZE:
            return TextEditorMutationResult(
                new_state=state,
                action_result=OpenFileResult(
                    success=False,
                    error=f"This request would result in {state.total_lines() + added_lines} open lines exceeding the maximum of {self.MAX_OPEN_SIZE} lines.",
                ),
            )

        new_open_files = dict(state.open_files)
        new_open_files[path] = new_open_file_state
        new_state = TextEditorState(open_files=new_open_files)

        return TextEditorMutationResult(
            new_state=new_state,
            action_result=OpenFileResult(success=True, error=""),
        )

    def close_file_range(
        self, state: TextEditorState, path: str, start_line: int, n_lines: int
    ) -> TextEditorMutationResult[None]:
        open_file_state = state.open_files[path]
        new_open_file_state = open_file_state.subtract_range(
            LineRange(start_line, n_lines)
        )

        new_open_files = dict(state.open_files)
        if new_open_file_state.total_lines() == 0:
            del new_open_files[path]
        else:
            new_open_files[path] = new_open_file_state

        new_state = TextEditorState(open_files=new_open_files)
        return TextEditorMutationResult(new_state=new_state, action_result=None)

    def replace_file_lines(
        self,
        state: TextEditorState,
        path: str,
        replacements: list[LineRangeReplacement],
    ) -> TextEditorMutationResult[WriteFileResult]:
        file_io_context = get_io_context()

        # Check if the file is open
        open_file_state = state.open_files.get(path)
        if not open_file_state:
            return TextEditorMutationResult(
                new_state=state,
                action_result=WriteFileResult(
                    success=False,
                    error=f"The file {path} is not open.",
                ),
            )

        # Check if all ranges are open
        missing_ranges = []
        for replacement in replacements:
            if not open_file_state.is_range_open(
                replacement["start_line"], replacement["n_lines"]
            ):
                missing_ranges.append(replacement)
        if missing_ranges:
            return TextEditorMutationResult(
                new_state=state,
                action_result=WriteFileResult(
                    success=False,
                    error=f"The following ranges are not open: {missing_ranges}",
                ),
            )

        # Sort replacements by start line
        replacements.sort(key=lambda x: x["start_line"])

        # Ensure replacements are non-overlapping
        for i in range(len(replacements) - 1):
            if (
                replacements[i]["start_line"] + replacements[i]["n_lines"]
                > replacements[i + 1]["start_line"]
            ):
                return TextEditorMutationResult(
                    new_state=state,
                    action_result=WriteFileResult(
                        success=False,
                        error=f"The following replacements are overlapping: {replacements[i]}, {replacements[i+1]}",
                    ),
                )

        all_new_lines = [l["lines"].rstrip("\n").split("\n") for l in replacements]

        net_change = sum(len(l) for l in all_new_lines) - sum(
            l["n_lines"] for l in replacements
        )
        if state.total_lines() + net_change > self.MAX_OPEN_SIZE:
            return TextEditorMutationResult(
                new_state=state,
                action_result=WriteFileResult(
                    success=False,
                    error=f"This edit would result in {state.total_lines() + net_change} open lines exceeding the maximum of {self.MAX_OPEN_SIZE} lines.",
                ),
            )

        file_io_context = get_io_context()
        try:
            file_contents = file_io_context.read_file(path)
            file_lines = file_contents.split("\n")
        except Exception as e:
            return TextEditorMutationResult(
                new_state=state,
                action_result=WriteFileResult(
                    success=False,
                    error=f"Failed to write to file: {str(e)}",
                ),
            )

        # Apply replacements in reverse order to indexes don't change while iterating
        for i, replacement in reversed(list(enumerate(replacements))):
            start_line = replacement["start_line"]
            n_lines = replacement["n_lines"]
            file_lines[start_line - 1 : start_line - 1 + n_lines] = all_new_lines[i]

        new_contents = "\n".join(file_lines)

        file_io_context.write_file(path, new_contents)
        return TextEditorMutationResult(
            new_state=state,
            action_result=WriteFileResult(success=True, error=""),
        )


class TextEditorStateful:
    def __init__(self, text_editor: TextEditor, initial_state: TextEditorState):
        self.text_editor = text_editor
        self.state = initial_state

    def open_file(self, path: str, start_line: int) -> OpenFileResult:
        result = self.text_editor.open_file(self.state, path, start_line)
        self.state = result.new_state
        return result.action_result

    def close_file_range(self, path: str, start_line: int, n_lines: int) -> None:
        result = self.text_editor.close_file_range(
            self.state, path, start_line, n_lines
        )
        self.state = result.new_state
        return result.action_result

    def replace_file_lines(
        self,
        path: str,
        replacements: list[LineRangeReplacement],
    ) -> WriteFileResult:
        result = self.text_editor.replace_file_lines(self.state, path, replacements)
        self.state = result.new_state
        return result.action_result


_text_editor_context: ContextVar[Optional[TextEditorStateful]] = ContextVar(
    "_text_editor_context", default=None
)


@contextmanager
def text_editor(context: TextEditorStateful):
    token = _text_editor_context.set(context)
    try:
        yield context
    finally:
        _text_editor_context.reset(token)


def require_text_editor() -> TextEditorStateful:
    context = _text_editor_context.get()
    assert context is not None
    return context


@weave.op
def open_file(path: str, start_line: int) -> str:
    """Open a buffer of lines from the given file.

    Args:
        path: The path to the file.
        start_line: The line number to start reading from (1-indexed).

    Returns:
        "success" if the file was opened successfully,
        "error: <error message>" if the file was not opened successfully.
    """
    text_editor = require_text_editor()
    response = text_editor.open_file(path, start_line)
    if response.success:
        return "success"
    else:
        return f"error: {response.error}"


@weave.op
def close_file_range(path: str, start_line: int, n_lines: int) -> str:
    """Close a buffer of lines from the given file.

    Args:
        path: The path to the file.
        start_line: The line number to start reading from (1-indexed).
        n_lines: The number of lines to close.

    Returns:
        "success" if the file was closed successfully.
    """
    text_editor = require_text_editor()
    response = text_editor.close_file_range(path, start_line, n_lines)
    return "success"


class LineRangeReplacementStartEnd(TypedDict):
    start_line: int
    remove_up_to_line: int
    lines: str


@weave.op
def replace_file_lines(
    path: str, replacements: list[LineRangeReplacementStartEnd]
) -> str:
    """Replace ranges of lines within a file. Changes must be made to open ranges, and will be reflected immediately on the filesystem. First, existing lines are removed starting at start line, up to but not including replace_up_to_line. Then the new lines are added in that position.

    Args:
        path: The path to the file.
        replacements: A list of replacements to make. Each replacement is a dictionary with keys: start_line (1-indexed, inclusive), remove_up_to_line (1-indexed, exclusive), lines (a string of newline separated lines to insert)

    Returns:
        "success" if the file was replaced successfully,
        "error: <error message>" if the file was not replaced successfully.
    """
    text_editor = require_text_editor()
    replacements_list = [
        LineRangeReplacement(
            start_line=r["start_line"],
            n_lines=r["remove_up_to_line"] - r["start_line"],
            lines=r["lines"],
        )
        for r in replacements
    ]
    response = text_editor.replace_file_lines(path, replacements_list)
    if response.success:
        return "success"
    else:
        return f"error: {response.error}"
