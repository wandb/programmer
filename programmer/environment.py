from dataclasses import dataclass
from typing import Protocol
from contextvars import ContextVar
from contextlib import contextmanager

from .git import GitRepo

@dataclass
class EnvironmentSnapshotKey:
    env_id: str
    snapshot_info: dict


class Environment(Protocol):
    def start_session(self, session_id: str): ...

    def finish_session(self): ...

    def make_snapshot(self, message: str) -> EnvironmentSnapshotKey: ...

    @classmethod
    def restore_from_snapshot_key(cls, ref: EnvironmentSnapshotKey): ...


@contextmanager
def environment_session(env: Environment, session_id: str | None):
    if session_id is not None:
        env.start_session(session_id)
        token = environment_context.set(env)
        try:
            yield env
        finally:
            env.finish_session()
            environment_context.reset(token)
    else:
        yield env


def get_current_environment() -> Environment:
    return environment_context.get()


class GitEnvironment(Environment):
    def __init__(self, repo: GitRepo):
        self.repo = repo
        self.original_git_ref = None
        self.programmer_branch = None

    def start_session(self, session_id: str):
        self.original_git_ref = self.repo.get_current_head()
        self.programmer_branch = f"programmer-{session_id}"
        print("programmer_branch:", self.programmer_branch)
        # Create the programmer branch based on the current state
        self.repo.create_branch(self.programmer_branch)

    def finish_session(self):
        if self.original_git_ref is None or self.programmer_branch is None:
            raise ValueError("Session not started")
        # No need to checkout back as we never changed the branch

    def make_snapshot(self, message: str) -> EnvironmentSnapshotKey:
        if self.programmer_branch is None:
            raise ValueError("Programmer branch is not set")
        # Commit directly to the programmer branch using new method
        commit_hash = self.repo.commit_directly_to_branch(self.programmer_branch, message)
        return EnvironmentSnapshotKey(
            "git", {"origin": self.repo.get_origin_url(), "commit": commit_hash}
        )

    @classmethod
    def restore_from_snapshot_key(cls, ref: EnvironmentSnapshotKey):
        origin = ref.snapshot_info["origin"]
        commit = ref.snapshot_info["commit"]
        repo = GitRepo.from_current_dir()
        if not repo:
            raise ValueError("No git repo found")
        if origin != repo.get_origin_url():
            raise ValueError("Origin URL mismatch")
        repo.checkout_existing(commit)
        print("Checked out commit", commit)


class NoopEnvironment(Environment):
    def start_session(self, session_id: str):
        pass

    def finish_session(self):
        pass

    def make_snapshot(self, message: str) -> EnvironmentSnapshotKey:
        return EnvironmentSnapshotKey("noop", {})

    @classmethod
    def restore_from_snapshot_key(cls, ref: EnvironmentSnapshotKey):
        pass


def restore_environment(snapshot_key: EnvironmentSnapshotKey) -> Environment:
    if snapshot_key.env_id == "git":
        GitEnvironment.restore_from_snapshot_key(snapshot_key)
    return NoopEnvironment()


environment_context: ContextVar[Environment] = ContextVar(
    "environment", default=NoopEnvironment()
)
