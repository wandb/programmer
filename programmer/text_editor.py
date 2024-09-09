from typing import Optional, Generic, TypeVar
from dataclasses import dataclass, field

from .io_context import get_current_context


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


@dataclass(frozen=True)
class TextEditorState:
    open_files: dict[str, OpenFileState] = field(default_factory=dict)

    def total_lines(self) -> int:
        return sum(file.total_lines() for file in self.open_files.values())

    def get_open_file_info(self) -> "OpenFileInfoResult":
        file_io_context = get_current_context()
        open_file_buffers = {}
        for path, open_file in self.open_files.items():
            contents = file_io_context.read_file(path)
            lines = contents.split("\n")
            buffers = []
            for range in open_file.ranges:
                buffer = Buffer(
                    line_range=range,
                    lines=lines[range.start_line : range.start_line + range.n_lines],
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
        lines = ["The following file line ranges are currently open"]
        for path, open_file_info in self.open_file_buffers.items():
            lines.append(f"<file {path}>")
            lines.append(f"<file_info total_lines={open_file_info.total_lines} />")
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
        file_io_context = get_current_context()
        try:
            file_contents = file_io_context.read_file(path)
        except FileNotFoundError:
            return TextEditorMutationResult(
                new_state=state,
                action_result=OpenFileResult(success=False, error="File not found"),
            )

        file_lines = file_contents.split("\n")
        file_lines_count = len(file_lines)

        if start_line >= file_lines_count:
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
        start_line: int,
        truncate_n_lines: int,
        lines: str,
    ) -> TextEditorMutationResult[WriteFileResult]:
        file_io_context = get_current_context()
        new_lines = lines.split("\n")
        net_change = len(new_lines) - truncate_n_lines
        if state.total_lines() + net_change > self.MAX_OPEN_SIZE:
            return TextEditorMutationResult(
                new_state=state,
                action_result=WriteFileResult(
                    success=False,
                    error=f"This edit would result in {state.total_lines() + net_change} open lines exceeding the maximum of {self.MAX_OPEN_SIZE} lines.",
                ),
            )

        try:
            file_contents = file_io_context.read_file(path)
            file_lines = file_contents.split("\n")
            file_lines[start_line : start_line + truncate_n_lines] = new_lines
            new_contents = "\n".join(file_lines)
            file_io_context.write_file(path, new_contents)
        except Exception as e:
            return TextEditorMutationResult(
                new_state=state,
                action_result=WriteFileResult(
                    success=False,
                    error=f"Failed to write to file: {str(e)}",
                ),
            )

        new_open_files = dict(state.open_files)
        if path not in new_open_files:
            new_open_files[path] = OpenFileState()

        new_range = LineRange(start_line, len(new_lines))
        new_open_files[path] = (
            new_open_files[path]
            .subtract_range(LineRange(start_line, truncate_n_lines))
            .add_range(new_range)
        )

        new_state = TextEditorState(open_files=new_open_files)
        return TextEditorMutationResult(
            new_state=new_state,
            action_result=WriteFileResult(success=True, error=""),
        )
