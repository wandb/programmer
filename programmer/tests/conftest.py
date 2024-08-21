from typing import Generator
import warnings
import pytest

# Disable the specific DeprecationWarning for distutils
warnings.filterwarnings(
    "ignore",
    category=DeprecationWarning,
    message="The distutils package is deprecated and slated for removal",
)

# Disable SentryHubDeprecationWarning
warnings.filterwarnings(
    "ignore",
    category=DeprecationWarning,  # or use SentryHubDeprecationWarning if it's a custom category
    message="`sentry_sdk.Hub` is deprecated and will be removed",
)

# Disable Jupyter platformdirs warning
warnings.filterwarnings(
    "ignore",
    category=DeprecationWarning,
    message="Jupyter is migrating its paths to use standard platformdirs",
)

from weave.weave_client import WeaveClient
from weave.trace_server.sqlite_trace_server import SqliteTraceServer
from weave.weave_init import InitializedClient


@pytest.fixture()
def weave_client() -> Generator[WeaveClient, None, None]:
    entity = "pytest"
    project = "test-project"
    sqlite_server = SqliteTraceServer("file::memory:?cache=shared")
    sqlite_server.drop_tables()
    sqlite_server.setup_tables()
    client = WeaveClient(entity, project, sqlite_server)
    inited_client = InitializedClient(client)
    # weave fixture does autopatch.autopatch, do we want that here?
    try:
        yield inited_client.client
    finally:
        inited_client.reset()
