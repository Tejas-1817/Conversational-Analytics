from typing import Protocol
from sqlalchemy.engine import Connection, Engine, URL

class DatabaseAdapter(Protocol):
    source_type: str
    sqlglot_dialect: str
    default_port: int | None
    default_schema: str | None

    def build_url(self, source, password: str) -> URL | str: ...
    def create_engine(self, source, password: str) -> Engine: ...
    def verify_read_only(self, engine: Engine) -> None: ...
    def preflight(
        self,
        connection: Connection,
        sql: str,
        timeout_ms: int,
    ) -> None: ...
    def connection_context(
        self,
        connection: Connection,
    ) -> tuple[str, str]: ...