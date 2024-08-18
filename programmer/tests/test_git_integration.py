import pytest
import tempfile
import shutil
import os
from git import Repo
from programmer.git import GitRepo


@pytest.fixture
def setup_repo():
    # Create a temporary directory for the repository
    test_dir = tempfile.mkdtemp()
    repo = Repo.init(test_dir)
    git_repo = GitRepo(repo)

    # Set up user config for the test repo
    with repo.config_writer() as config:
        config.set_value("user", "name", "Test User")
        config.set_value("user", "email", "test@example.com")

    # Create an initial commit so HEAD exists
    initial_file_path = os.path.join(test_dir, "initial.txt")
    with open(initial_file_path, "w") as f:
        f.write("Initial content")
    repo.index.add([initial_file_path])
    repo.index.commit("Initial commit")

    # Create and checkout the main branch
    main_branch = repo.create_head('main')
    main_branch.checkout()

    yield repo, git_repo, test_dir

    # Remove the temporary directory after the test
    shutil.rmtree(test_dir)


def test_commit_directly_to_branch(setup_repo):
    repo, git_repo, test_dir = setup_repo

    # Create and commit a file in the main branch
    file_path = os.path.join(test_dir, "test_file.py")
    with open(file_path, "w") as f:
        f.write("print('Hello, world!')\n")

    repo.index.add([file_path])
    repo.index.commit("Initial commit on main")

    # Modify the file
    with open(file_path, "a") as f:
        f.write("print('Another line')\n")

    # Commit changes to the programmer-<session> branch
    session_branch_name = "programmer-session"
    git_repo.create_branch(session_branch_name)
    commit_message = "Commit from programmer session"
    git_repo.commit_directly_to_branch(session_branch_name, commit_message)

    # Verify the commit in the programmer-<session> branch
    session_branch_commit = repo.commit(session_branch_name)
    tree_files = session_branch_commit.tree.traverse()
    file_names = [item.path for item in tree_files]

    assert "test_file.py" in file_names

    # Verify the content of the file in the commit
    blob_data = (
        session_branch_commit.tree["test_file.py"].data_stream.read().decode("utf-8")
    )
    assert "print('Another line')" in blob_data

    # Verify that the main branch is unaffected
    main_branch_commit = repo.commit("main")
    assert main_branch_commit.hexsha != session_branch_commit.hexsha


def test_no_empty_commit(setup_repo):
    repo, git_repo, _ = setup_repo

    # Create and checkout the programmer-<session> branch
    session_branch_name = "programmer-session"
    git_repo.create_branch(session_branch_name)

    # Commit changes to the programmer-<session> branch
    commit_message = "Commit from programmer session"
    initial_commit_sha = repo.commit(session_branch_name).hexsha
    commit_sha = git_repo.commit_directly_to_branch(session_branch_name, commit_message)

    # Verify that the SHA returned is equal to the initial commit SHA
    assert initial_commit_sha == commit_sha

    # Verify no new commit is created
    new_commit_sha = repo.commit(session_branch_name).hexsha
    assert initial_commit_sha == new_commit_sha


def test_multiple_commits_with_empty(setup_repo):
    repo, git_repo, test_dir = setup_repo

    # Create and checkout the programmer-<session> branch
    session_branch_name = "programmer-session"
    git_repo.create_branch(session_branch_name)
    initial_commit_sha = repo.commit(session_branch_name).hexsha

    # First commit (empty)
    commit_message = "First empty commit"
    commit_sha_1 = git_repo.commit_directly_to_branch(session_branch_name, commit_message)
    assert commit_sha_1 == initial_commit_sha

    # Second commit (non-empty)
    file_path = os.path.join(test_dir, "test_file.py")
    with open(file_path, "w") as f:
        f.write("print('Hello, world!')\n")

    git_repo.commit_directly_to_branch(session_branch_name, "Second commit with changes")
    commit_sha_2 = repo.commit(session_branch_name).hexsha
    assert commit_sha_2 != initial_commit_sha

    # Third commit (empty)
    commit_sha_3 = git_repo.commit_directly_to_branch(session_branch_name, "Third empty commit")
    assert commit_sha_3 == commit_sha_2
    assert commit_sha_3 != initial_commit_sha
