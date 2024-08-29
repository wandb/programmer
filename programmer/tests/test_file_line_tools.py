import os
import pytest
from tempfile import TemporaryDirectory
from programmer.tools import (
    read_lines_from_file,
    splice_lines_in_file,
    LocalToolContext,
    tool_context,
    get_current_context,
)


@pytest.fixture()
def tempdir_tool_context():
    with TemporaryDirectory() as tmpdir:
        with tool_context(LocalToolContext(tmpdir)) as tc:
            yield tc


@pytest.fixture()
def test_file_path(tempdir_tool_context):
    file_path = "test_file.txt"
    tempdir_tool_context.write_file(
        file_path,
        "Line 1\nLine 2\nLine 3\nLine 4\nLine 5\nLine 6\nLine 7\nLine 8\nLine 9\nLine 10\n",
    )
    yield file_path


def test_read_lines_from_file(test_file_path):
    # Valid read
    result = read_lines_from_file(test_file_path, 1)
    assert result.startswith("1:Line 1\n")
    assert "10:Line 10\n" in result

    # Reading from a middle line
    result = read_lines_from_file(test_file_path, 5)
    assert result.startswith("5:Line 5\n")
    assert "10:Line 10\n" in result

    # Invalid start_line
    with pytest.raises(Exception, match="Invalid start_line number."):
        read_lines_from_file(test_file_path, 0)

    with pytest.raises(Exception, match="Invalid start_line number."):
        read_lines_from_file(test_file_path, 11)


def test_replace_lines_in_file(test_file_path):
    # Valid replacement
    result = splice_lines_in_file(
        test_file_path,
        2,
        3,
        "Line 2\nLine 3\nLine 4\n",
        "New Line 2\nNew Line 3\nNew Line 4\n",
    )
    assert "1:Line 1\n" in result
    assert "2:New Line 2\n" in result
    assert "4:New Line 4\n" in result
    assert "10:Line 10\n" in result

    # Replacement with a new file
    result = splice_lines_in_file(
        "new_test_file.txt", 1, 0, "", "First Line\nSecond Line\n"
    )
    assert "1:First Line\n" in result
    assert "2:Second Line\n" in result

    splice_lines_in_file(test_file_path, 11, 0, "", "Out of range\n")


# Test appending to the end of a file
def test_append_to_file(tempdir_tool_context, test_file_path):
    # Read the original content
    original_content = tempdir_tool_context.read_file(test_file_path)

    # Append new lines
    new_lines = "New Line 11\nNew Line 12\n"
    result = splice_lines_in_file(test_file_path, 11, 0, "", new_lines)

    # Verify the file content
    updated_content = tempdir_tool_context.read_file(test_file_path)

    assert updated_content == original_content + new_lines

    # Verify that the original content is preserved
    assert original_content in updated_content

    # Check that we can still read all lines including the new ones
    all_lines = read_lines_from_file(test_file_path, 1)
    assert "1:Line 1\n" in all_lines
    assert "10:Line 10\n" in all_lines
    assert "11:New Line 11\n" in all_lines
    assert "12:New Line 12\n" in all_lines


# Test inserting at the beginning of an existing file
def test_insert_at_beginning(tempdir_tool_context, test_file_path):
    # Read the original content
    original_content = tempdir_tool_context.read_file(test_file_path)

    # Insert new lines at the beginning
    new_lines = "New First Line\nNew Second Line\n"
    result = splice_lines_in_file(test_file_path, 1, 0, "", new_lines)

    # Verify the result
    assert "1:New First Line\n" in result
    assert "2:New Second Line\n" in result
    assert "3:Line 1\n" in result

    # Verify the file content
    updated_content = tempdir_tool_context.read_file(test_file_path)

    assert updated_content == new_lines + original_content

    # Check that we can read all lines including the new ones
    all_lines = read_lines_from_file(test_file_path, 1)
    assert "1:New First Line\n" in all_lines
    assert "2:New Second Line\n" in all_lines
    assert "3:Line 1\n" in all_lines
    assert "12:Line 10\n" in all_lines  # Original last line is now at position 12


# Test reading, replacing, and reading again
def test_read_replace_read(test_file_path):
    # Read the original content
    original_content = read_lines_from_file(test_file_path, 1)

    # Verify some original content
    assert "1:Line 1\n" in original_content
    assert "5:Line 5\n" in original_content
    assert "10:Line 10\n" in original_content

    # Replace lines 3-5 with new content
    new_lines = "Replaced Line 3\nReplaced Line 4\nReplaced Line 5\n"
    replace_result = splice_lines_in_file(
        test_file_path, 3, 3, "Line 3\nLine 4\nLine 5\n", new_lines
    )

    # Verify the replace result
    assert "3:Replaced Line 3\n" in replace_result
    assert "4:Replaced Line 4\n" in replace_result
    assert "5:Replaced Line 5\n" in replace_result
    assert "6:Line 6\n" in replace_result  # Original Line 6 is now at position 6

    # Read the updated content
    updated_content = read_lines_from_file(test_file_path, 1)

    # Verify the updated content
    assert "1:Line 1\n" in updated_content
    assert "2:Line 2\n" in updated_content
    assert "3:Replaced Line 3\n" in updated_content
    assert "4:Replaced Line 4\n" in updated_content
    assert "5:Replaced Line 5\n" in updated_content
    assert "6:Line 6\n" in updated_content
    assert (
        "10:Line 10\n" in updated_content
    )  # Original last line is still at position 10
