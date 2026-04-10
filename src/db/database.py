from __future__ import annotations

import mysql.connector
from mysql.connector import MySQLConnection

from config.settings import MYSQL_CONFIG

_connection: MySQLConnection | None = None


def get_connection() -> MySQLConnection:
    global _connection
    if _connection is not None and _connection.is_connected():
        return _connection

    # Ensure the database exists before connecting to it
    _ensure_database()

    _connection = mysql.connector.connect(**MYSQL_CONFIG)
    return _connection


def _ensure_database() -> None:
    """Create the database if it doesn't exist yet."""
    cfg = {k: v for k, v in MYSQL_CONFIG.items() if k != "database"}
    conn = mysql.connector.connect(**cfg)
    cursor = conn.cursor()
    cursor.execute(
        f"CREATE DATABASE IF NOT EXISTS `{MYSQL_CONFIG['database']}` "
        "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
    )
    cursor.close()
    conn.close()


def close_connection() -> None:
    global _connection
    if _connection is not None:
        _connection.close()
        _connection = None
