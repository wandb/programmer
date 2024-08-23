from typing import Generator
import warnings
import pytest
import logging

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
