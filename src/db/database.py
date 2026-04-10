from __future__ import annotations

from pathlib import Path

import duckdb

from config.settings import DB_PATH

_connection: duckdb.DuckDBPyConnection | None = None


def get_connection(db_path: Path | None = None) -> duckdb.DuckDBPyConnection:
    global _connection
    if _connection is not None:
        return _connection

    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    _connection = duckdb.connect(str(path))
    return _connection


def close_connection() -> None:
    global _connection
    if _connection is not None:
        _connection.close()
        _connection = None
