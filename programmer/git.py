from git import Repo, InvalidGitRepositoryError, GitCommandError
import shutil
import os
import tempfile
from typing import List, Union


def get_current_repo() -> Repo:
    """
    Get the current Git repository from the current working directory or its parent directories.

    Returns:
        The Repo object representing the current Git repository.

    Raises:
        InvalidGitRepositoryError: If the current directory is not within a Git repository.
    """
    try:
        return Repo(os.getcwd(), search_parent_directories=True)
    except InvalidGitRepositoryError:
        raise InvalidGitRepositoryError(
            "Current directory is not within a Git repository."
        )


def checkout_new_branch(branch_name: str) -> None:
    """
    Create and checkout a new Git branch with the given name.
    This operation will fail if the branch already exists.

    Args:
        branch_name: Name of the branch to create and checkout.

    Raises:
        GitCommandError: If the branch already exists.
    """
    repo = get_current_repo()
    git = repo.git
    # Attempt to create and checkout the new branch
    git.checkout(b=branch_name)


def add_and_commit(paths: List[str], message: str) -> str:
    """
    Add changes to the Git index for the specified paths and commit them with a message.

    Args:
        paths: List of paths to add to the Git index.
        message: Commit message.

    Returns:
        The commit ID of the new commit.
    """
    repo = get_current_repo()
    index = repo.index
    index.add(paths)
    commit = index.commit(message)
    return commit.hexsha


def get_current_head() -> Union[str, None]:
    """
    Get the current HEAD of the repository, which is either the branch name or the commit SHA.

    Returns:
        The branch name if on a branch, otherwise the commit SHA.
    """
    repo = get_current_repo()
    if repo.head.is_detached:
        return str(repo.head.commit.hexsha)
    else:
        return str(repo.active_branch.name)


def copy_files_to_new_branch_or_commit(paths: List[str], new_ref: str) -> None:
    """
    Copy specified files from the current branch, switch to a new branch or commit, and
    copy those files into the new branch or commit.

    Args:
        paths: List of file paths to copy.
        new_ref: The name of the new branch to create or the commit SHA to checkout.

    Raises:
        FileNotFoundError: If any of the specified paths do not exist.
        GitCommandError: If there are issues with Git operations.
    """
    repo = get_current_repo()
    current_files = {path: os.path.join(repo.working_tree_dir, path) for path in paths}

    # Create a temporary directory to store backups
    with tempfile.TemporaryDirectory() as temp_dir:
        backup_files = {
            path: os.path.join(temp_dir, os.path.basename(path)) for path in paths
        }

        # Copy files to temporary backup
        for path in paths:
            if not os.path.exists(current_files[path]):
                raise FileNotFoundError(f"{path} does not exist in the current branch.")
            shutil.copy2(current_files[path], backup_files[path])

        # Checkout the new branch or commit
        try:
            repo.git.checkout(new_ref)
        except GitCommandError as e:
            raise e

        # Restore files from backup
        for path in paths:
            shutil.copy2(backup_files[path], current_files[path])
