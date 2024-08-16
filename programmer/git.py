from git import Repo, InvalidGitRepositoryError, GitCommandError
import shutil
import os
import tempfile
from typing import List, Union, Optional


class GitRepo:
    def __init__(self, repo: Repo):
        self.repo = repo

    @classmethod
    def from_current_dir(cls) -> Optional["GitRepo"]:
        """
        Create a GitRepo instance from the current working directory or its parent directories.

        Returns:
            GitRepo instance if in a Git repository, None otherwise.
        """
        try:
            repo = Repo(os.getcwd(), search_parent_directories=True)
            return cls(repo)
        except InvalidGitRepositoryError:
            return None

    def checkout(self, branch_name: str) -> None:
        """
        Create and checkout a new Git branch with the given name.
        If the branch already exists, it will be checked out.

        Args:
            branch_name: Name of the branch to create and checkout.
        """
        try:
            self.repo.git.checkout(b=branch_name)
        except GitCommandError:
            # Branch already exists, so just check it out
            self.repo.git.checkout(branch_name)

    def add_path(self, path: str) -> None:
        """
        Add a single path to the Git index if it's within the repository.

        Args:
            path: The path to add to the Git index.
        """
        repo_root = self.repo.working_tree_dir
        abs_path = os.path.abspath(path)

        if abs_path.startswith(repo_root):
            self.repo.index.add([abs_path])

    def commit(self, message: str) -> str:
        """
        Commit the current changes and return the commit SHA.

        Args:
            message: The commit message.

        Returns:
            The SHA of the new commit if changes were committed,
            or the current HEAD's SHA if no changes were made.

        Raises:
            GitCommandError: If there are issues with Git operations.
        """
        if self.repo.is_dirty():
            self.repo.index.commit(message)
        return self.repo.head.commit.hexsha

    def get_current_head(self) -> str:
        """
        Get the current HEAD of the repository, which is either the branch name or the commit SHA.

        Returns:
            The branch name if on a branch, otherwise the commit SHA.
        """
        if self.repo.head.is_detached:
            return str(self.repo.head.commit.hexsha)
        else:
            return str(self.repo.active_branch.name)

    def copy_paths_from_ref(self, paths: List[str], ref: str) -> None:
        """
        Copy specified files from a git reference to the current working state.

        Args:
            paths: List of file paths to copy.
            ref: The git reference (branch, tag, or commit SHA) to copy from.

        Raises:
            GitCommandError: If there are issues with Git operations.
            FileNotFoundError: If any of the specified paths do not exist in the given ref.
        """
        for path in paths:
            rel_path = os.path.relpath(path, self.repo.working_tree_dir)
            if rel_path.startswith(".."):
                continue

            file_content = self.repo.git.show(f"{ref}:{rel_path}")

            with open(os.path.join(self.repo.working_tree_dir, path), "w") as f:
                f.write(file_content)


def get_git_repo() -> Optional[GitRepo]:
    """
    Get a GitRepo instance for the current directory or its parent directories.

    Returns:
        GitRepo instance if in a Git repository, None otherwise.
    """
    return GitRepo.from_current_dir()


def is_git_repo() -> bool:
    """
    Check if the current directory is within a Git repository.

    Returns:
        True if the current directory is within a Git repository, False otherwise.
    """
    return get_git_repo() is not None
