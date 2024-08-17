from git import Repo, InvalidGitRepositoryError, GitCommandError
import os
from typing import Optional
import tempfile
import shutil


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

    def get_origin_url(self) -> Optional[str]:
        """
        Get the remote URL (e.g., GitHub URL) for this repository.

        Returns:
            The remote URL as a string if it exists, None otherwise.
        """
        try:
            remote_url = self.repo.remotes.origin.url
            return remote_url if remote_url else None
        except AttributeError:
            # No remote named 'origin' exists
            return None

    def checkout_existing(self, ref: str) -> None:
        self.repo.git.checkout(ref)

    def checkout_new(self, branch_name: str) -> None:
        self.repo.git.checkout(b=branch_name)

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

    def checkout_and_copy(self, to_ref: str) -> None:
        current_branch = self.get_current_head()

        with tempfile.TemporaryDirectory() as temp_dir:
            # Get all changed files between current branch and to_ref
            changed_files = self.repo.git.diff(
                "--name-only", current_branch, to_ref
            ).splitlines()

            # Copy changed files to the temp directory
            for file in changed_files:
                src_path = os.path.join(self.repo.working_tree_dir, file)
                dst_path = os.path.join(temp_dir, file)
                os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                if os.path.exists(src_path):
                    shutil.copy2(src_path, dst_path)

            # Checkout the target branch
            self.repo.git.checkout(to_ref)

            # Copy files from temp directory to the working directory
            for root, _, files in os.walk(temp_dir):
                for file in files:
                    src_path = os.path.join(root, file)
                    rel_path = os.path.relpath(src_path, temp_dir)
                    dst_path = os.path.join(self.repo.working_tree_dir, rel_path)
                    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                    shutil.copy2(src_path, dst_path)

    def add_all_and_commit(self, message: str) -> str:
        """
        Add all files (including untracked ones) and commit them.

        Args:
            message: The commit message.

        Returns:
            The SHA of the new commit if changes were committed,
            or the current HEAD's SHA if no changes were made.

        Raises:
            GitCommandError: If there are issues with Git operations.
        """
        # Add all files, including untracked ones
        self.repo.git.add(A=True)

        # Check if there are changes to commit
        if self.repo.is_dirty(untracked_files=True):
            # Commit the changes
            commit = self.repo.index.commit(message)
            return commit.hexsha
        else:
            # If no changes, return the current HEAD's SHA
            return self.repo.head.commit.hexsha
