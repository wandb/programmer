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
    def start_session(self, session_id: str):
        ...

    def finish_session(self):
        ...

    def make_snapshot(self, message: str) -> EnvironmentSnapshotKey:
        ...

    @classmethod
    def restore_from_snapshot_key(cls, ref: EnvironmentSnapshotKey):
        ...


@contextmanager
def set_environment(env: Environment):
    token = environment_context.set(env)
    try:
        yield env
    finally:
        environment_context.reset(token)


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
        self.repo.checkout(self.programmer_branch)

    def finish_session(self):
        if self.original_git_ref is None or self.programmer_branch is None:
            raise ValueError("Session not started")
        self.repo.checkout(self.original_git_ref)
        self.repo.copy_all_from_ref(self.programmer_branch)

    def make_snapshot(self, message: str) -> EnvironmentSnapshotKey:
        commit_hash = self.repo.add_all_and_commit(message)
        return EnvironmentSnapshotKey(
            'git', {
                'origin': self.repo.get_origin_url(),
                'commit': commit_hash
            })

    @classmethod
    def restore_from_snapshot_key(cls, ref: EnvironmentSnapshotKey):
        origin = ref.snapshot_info['origin']
        commit = ref.snapshot_info['commit']
        repo = GitRepo.from_current_dir()
        if not repo:
            raise ValueError("No git repo found")
        if origin != repo.get_origin_url():
            raise ValueError("Origin URL mismatch")
        repo.checkout(commit)   
        print("Checked out commit", commit)
        return cls(repo)


class NoopEnvironment(Environment):
    def start_session(self, session_id: str):
        pass

    def finish_session(self):
        pass

    def make_snapshot(self, message: str):
        pass

    @classmethod
    def restore_from_snapshot_key(cls, ref: str):
        pass


def init_environment() -> Environment:
    git_repo = GitRepo.from_current_dir()
    if git_repo:
        return GitEnvironment(git_repo)
    return NoopEnvironment()

def restore_environment(snapshot_key: EnvironmentSnapshotKey) -> Environment:
    if snapshot_key.env_id == 'git':
        return GitEnvironment.restore_from_snapshot_key(snapshot_key)
    return NoopEnvironment()

environment_context: ContextVar[Environment] = ContextVar(
    "environment", default=NoopEnvironment()
)
