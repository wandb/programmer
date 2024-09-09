import pytest
from tempfile import TemporaryDirectory
from programmer.text_editor import (
    TextEditor,
    TextEditorState,
    OpenFileState,
    LineRange,
    OpenFileResult,
    WriteFileResult,
    TextEditorMutationResult,
)
from programmer.tools import LocalToolContext, tool_context


@pytest.fixture()
def tempdir_tool_context():
    with TemporaryDirectory() as tmpdir:
        with tool_context(LocalToolContext(tmpdir)) as tc:
            yield tc


@pytest.fixture()
def sample_file(tempdir_tool_context):
    file_path = "sample.txt"
    content = "\n".join(f"Line {i}" for i in range(1, 201))  # 200 lines
    tempdir_tool_context.write_file(file_path, content)
    return file_path


@pytest.fixture()
def text_editor(tempdir_tool_context):
    return TextEditor(tempdir_tool_context, max_open_size=150, open_chunk_size=50)


@pytest.fixture()
def initial_state():
    return TextEditorState()


def test_open_file(text_editor, sample_file, initial_state):
    result = text_editor.open_file(initial_state, sample_file, 0)
    assert isinstance(result, TextEditorMutationResult)
    assert isinstance(result.action_result, OpenFileResult)
    assert result.action_result.success
    assert sample_file in result.new_state.open_files
    assert (
        result.new_state.open_files[sample_file].total_lines() == 50
    )  # OPEN_CHUNK_SIZE


def test_open_file_exceed_max_size(tempdir_tool_context, sample_file):
    text_editor = TextEditor(tempdir_tool_context, max_open_size=75, open_chunk_size=50)
    initial_state = TextEditorState()

    # Open the file once (50 lines)
    result1 = text_editor.open_file(initial_state, sample_file, 0)
    assert result1.action_result.success

    # Try to open another chunk, which would exceed the max_open_size
    result2 = text_editor.open_file(result1.new_state, sample_file, 50)
    assert isinstance(result2.action_result, OpenFileResult)
    assert not result2.action_result.success
    assert "exceeding the maximum" in result2.action_result.error


def test_open_file_at_boundary(tempdir_tool_context, sample_file):
    text_editor = TextEditor(
        tempdir_tool_context, max_open_size=100, open_chunk_size=50
    )
    initial_state = TextEditorState()

    # Open exactly MAX_OPEN_SIZE lines
    result1 = text_editor.open_file(initial_state, sample_file, 0)
    result2 = text_editor.open_file(result1.new_state, sample_file, 50)
    assert result1.action_result.success and result2.action_result.success
    assert result2.new_state.total_lines() == 100  # MAX_OPEN_SIZE

    # Try to open one more line, which should fail
    result3 = text_editor.open_file(result2.new_state, sample_file, 99)
    assert not result3.action_result.success
    assert "exceeding the maximum" in result3.action_result.error


def test_replace_file_lines_at_boundary(text_editor, sample_file, initial_state):
    state1 = text_editor.open_file(initial_state, sample_file, 0).new_state
    state2 = text_editor.open_file(state1, sample_file, 50).new_state
    state3 = text_editor.open_file(state2, sample_file, 100).new_state

    # Replace 5 lines with 5 new lines (no net change)
    result = text_editor.replace_file_lines(state3, sample_file, 0, 5, "New Line\n" * 4)
    assert result.action_result.success

    # Try to replace 5 lines with 6 new lines (net increase of 1, should fail)
    result = text_editor.replace_file_lines(state3, sample_file, 0, 5, "New Line\n" * 5)
    assert not result.action_result.success
    assert "exceeding the maximum" in result.action_result.error


def test_close_file_range(text_editor, sample_file, initial_state):
    state1 = text_editor.open_file(initial_state, sample_file, 0).new_state
    result = text_editor.close_file_range(state1, sample_file, 0, 25)
    assert result.new_state.open_files[sample_file].total_lines() == 25


def test_get_open_file_info(text_editor, sample_file, initial_state):
    state1 = text_editor.open_file(initial_state, sample_file, 0).new_state
    info = state1.get_open_file_info(text_editor.file_system)
    assert sample_file in info.open_file_buffers
    assert info.open_file_buffers[sample_file].total_lines == 200
    assert len(info.open_file_buffers[sample_file].buffers) == 1
    assert info.open_file_buffers[sample_file].buffers[0].line_range.start_line == 0
    assert info.open_file_buffers[sample_file].buffers[0].line_range.n_lines == 50


def test_open_file_multiple_ranges(text_editor, sample_file, initial_state):
    state1 = text_editor.open_file(initial_state, sample_file, 0).new_state
    state2 = text_editor.open_file(state1, sample_file, 50).new_state
    assert len(state2.open_files[sample_file].ranges) == 1
    assert state2.open_files[sample_file].ranges[0].start_line == 0
    assert state2.open_files[sample_file].ranges[0].n_lines == 100


def test_open_file_beyond_end(text_editor, sample_file, initial_state):
    result = text_editor.open_file(initial_state, sample_file, 200)
    assert isinstance(result.action_result, OpenFileResult)
    assert not result.action_result.success
    assert "beyond the end of the file" in result.action_result.error


def test_open_file_at_end(text_editor, sample_file, initial_state):
    result = text_editor.open_file(initial_state, sample_file, 199)
    assert isinstance(result.action_result, OpenFileResult)
    assert result.action_result.success
    assert result.new_state.open_files[sample_file].total_lines() == 1


def test_open_file_near_end(text_editor, sample_file, initial_state):
    result = text_editor.open_file(initial_state, sample_file, 190)
    assert isinstance(result.action_result, OpenFileResult)
    assert result.action_result.success
    assert result.new_state.open_files[sample_file].total_lines() == 10
