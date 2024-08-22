from typing import Generator
import warnings
import pytest
import logging

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

# Must filter warnings above weave imports to prevent them logging in tests

from weave.weave_client import WeaveClient
from weave.trace_server.sqlite_trace_server import SqliteTraceServer
from weave.weave_init import InitializedClient
from programmer.weave_next.api import make_external_sql_server

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


@pytest.fixture()
def weave_client() -> Generator[WeaveClient, None, None]:
    project_id = "pytest-test-project"  # Directly use a safe project id
    logger.debug(f"Using project_id: {project_id}")
    sqlite_server = SqliteTraceServer("file::memory:?cache=shared")
    sqlite_server.drop_tables()
    sqlite_server.setup_tables()
    sqlite_server = make_external_sql_server(sqlite_server)
    client = WeaveClient("pytest", project_id, sqlite_server)
    logger.debug(f"Initialized WeaveClient with project_id: {client._project_id()}")
    inited_client = InitializedClient(client)
    # weave fixture does autopatch.autopatch, do we want that here?
    try:
        yield inited_client.client
    finally:
        inited_client.reset()
