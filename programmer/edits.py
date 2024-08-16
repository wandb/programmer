import os
from typing import List
from contextlib import contextmanager
from contextvars import ContextVar


class EditContext:
    def __init__(self):
        self.edited_files: List[str] = []

    def add_edited_file(self, file_path: str):
        absolute_path = os.path.abspath(file_path)
        if absolute_path not in self.edited_files:
            self.edited_files.append(absolute_path)


edit_context_var: ContextVar[EditContext] = ContextVar(
    "edit_context", default=EditContext()
)


@contextmanager
def track_edits():
    token = edit_context_var.set(EditContext())
    try:
        yield edit_context_var.get()
    finally:
        edit_context_var.reset(token)


def get_edit_context() -> EditContext:
    return edit_context_var.get()
