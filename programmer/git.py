from git import Repo, InvalidGitRepositoryError, GitCommandError
import os
from typing import Optional


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

    def copy_all_from_ref(self, ref: str) -> None:
        """
        Copy all files from a git reference to the current working state.

        Args:
            ref: The git reference (branch, tag, or commit SHA) to copy from.

        Raises:
            GitCommandError: If there are issues with Git operations.
        """
        ls_tree_output = self.repo.git.ls_tree("-r", ref)

        for line in ls_tree_output.splitlines():
            # Each line is in the format: <mode> <type> <object> <file>
            _, obj_type, obj_hash, file_path = line.split(None, 3)

            if obj_type == "blob":
                file_content = self.repo.git.show(f"{ref}:{file_path}")
                full_path = os.path.join(str(self.repo.working_tree_dir), file_path)

                os.makedirs(os.path.dirname(full_path), exist_ok=True)

                with open(full_path, "w") as f:
                    f.write(file_content)
                    # For some reason this was clobbering newlines, so
                    # add one. But if the original didn't have one, this
                    # will cause a diff.
                    if not file_content.endswith("\n"):
                        f.write("\n")

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
