# weave doesn't setup the sqlite server correctly, need to wrap in an ID converter

from typing import Optional
import base64

from weave.trace_server.external_to_internal_trace_server_adapter import (
    IdConverter,
    ExternalTraceServer,
)
from weave.trace_server.sqlite_trace_server import SqliteTraceServer


def b64_encode(s: str) -> str:
    return base64.b64encode(s.encode("ascii")).decode("ascii")


def b64_decode(s: str) -> str:
    return base64.b64decode(s.encode("ascii")).decode("ascii")


class DummyIdConverter(IdConverter):
    def ext_to_int_project_id(self, project_id: str) -> str:
        return b64_encode(project_id)

    def int_to_ext_project_id(self, project_id: str) -> Optional[str]:
        return b64_decode(project_id)

    def ext_to_int_run_id(self, run_id: str) -> str:
        return run_id

    def int_to_ext_run_id(self, run_id: str) -> str:
        return run_id

    def ext_to_int_user_id(self, user_id: str) -> str:
        return user_id

    def int_to_ext_user_id(self, user_id: str) -> str:
        return user_id


# Exposed for conftest.py
def make_external_sql_server(internal_server: SqliteTraceServer) -> ExternalTraceServer:
    return ExternalTraceServer(
        internal_server,
        DummyIdConverter(),
    )


def init_local_client() -> SqliteTraceServer:
    # TODO: implement
    raise NotImplementedError
