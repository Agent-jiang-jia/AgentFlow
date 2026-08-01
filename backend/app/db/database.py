"""SQLAlchemy 2 engine and session management."""

import sqlite3
from collections.abc import Generator
from pathlib import Path
from typing import cast

from sqlalchemy import URL, Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker


def _sqlite_url(database_path: Path) -> URL:
    return URL.create("sqlite+pysqlite", database=str(database_path))


def _configure_sqlite_connection(
    dbapi_connection: sqlite3.Connection, _connection_record: object
) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


class Database:
    """Own the SQLite engine and SQLAlchemy session factory."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.engine: Engine = create_engine(
            _sqlite_url(database_path),
            connect_args={"check_same_thread": False},
            pool_pre_ping=True,
        )
        event.listen(self.engine, "connect", _configure_sqlite_connection)
        self.session_factory = sessionmaker(
            bind=self.engine,
            class_=Session,
            autoflush=False,
            expire_on_commit=False,
        )

    def session(self) -> Generator[Session, None, None]:
        """Yield one session and always close it."""
        with self.session_factory() as db_session:
            yield db_session

    def is_healthy(self) -> bool:
        """Return whether SQLite accepts a simple read-only query."""
        try:
            with self.engine.connect() as connection:
                result = cast(int, connection.execute(text("SELECT 1")).scalar_one())
                return result == 1
        except Exception:
            return False

    def dispose(self) -> None:
        """Release pooled database connections."""
        self.engine.dispose()
