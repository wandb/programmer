import os
from git import Repo, InvalidGitRepositoryError, GitCommandError
from typing import Optional
import tempfile


class GitRepo:
    def __init__(self, repo: Repo):
        self.repo = repo

    @classmethod
    def from_current_dir(cls) -> Optional["GitRepo"]:
        try:
            repo = Repo(os.getcwd(), search_parent_directories=True)
            return cls(repo)
        except InvalidGitRepositoryError:
            return None

    def get_origin_url(self) -> Optional[str]:
        try:
            remote_url = self.repo.remotes.origin.url
            return remote_url if remote_url else None
        except AttributeError:
            return None

    def create_branch(self, branch_name: str) -> None:
        if branch_name not in self.repo.heads:
            # Create a new branch from the current HEAD
            self.repo.git.branch(branch_name, self.repo.head.commit.hexsha)

    def commit_directly_to_branch(self, branch_name: str, message: str) -> str:
        # Ensure the branch is initialized
        self.create_branch(branch_name)

        # Use a temporary index file to stage files without affecting the actual index.
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_index_file = os.path.join(temp_dir, "index")
            env = os.environ.copy()
            env["GIT_INDEX_FILE"] = temp_index_file

            # Add all files from the working directory to the temporary index
            self.repo.git.add(A=True, env=env)

            # Write the tree from the temporary index
            tree = self.repo.git.write_tree(env=env)

            # Determine the parent commit
            parent_commit = self.repo.commit(branch_name)

            print(
                f"Committing to branch {branch_name}, parent commit: {parent_commit.hexsha}"
            )

            # Set author information using environment variables
            env["GIT_AUTHOR_NAME"] = "programmer"
            env["GIT_AUTHOR_EMAIL"] = "programmer-noreply@example.com"

            # Use the Repo's git command interface to create a commit-tree
            commit_hash = self.repo.git.commit_tree(tree,
                                                    '-p', parent_commit.hexsha,
                                                    '-m', message,
                                                    env=env)

            # Update the branch reference to point to the new commit
            self.repo.git.update_ref(f"refs/heads/{branch_name}", commit_hash)

            return commit_hash

    def get_current_head(self) -> str:
        if self.repo.head.is_detached:
            return str(self.repo.head.commit.hexsha)
        else:
            return str(self.repo.active_branch.name)
