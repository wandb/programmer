Author: Shawn

We need to build some new tool functions for programmer to do finer grained edits to files.

I want to add two functions to programmer/tools.py:

Line numbers are 1-indexed

*read_lines_from_file(file_path, start_line)*

this should read up to 500 lines from the file, starting at the given line number.

lines should be prefixed with "<line_number>:"

return value is a string

*replace_lines_in_file(file_path, start_line, end_line, new_lines)*

for the file at file_path, replace the lines from start_line (inclusive) to end_line (exclusive) with the new_lines.

new_lines is a string, not a list of lines.

returns the modified region in the same format as read_lines_from_file, with a 5-line buffer on either side of the modified region

if the file does not exist, this can be used to create a new file by setting start_line to 1 and end_line to 1.

invalid line ranges should cause an exception.


## additional requirements

These functions need to have python typing types, doc strings in the correct format, and throw actionable Exception messages, as they will be used by an LLM.

And we need comprehensive unit tests that check all the edge cases