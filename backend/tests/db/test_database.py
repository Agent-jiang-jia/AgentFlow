"""SQLite and Alembic foundation tests."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from app.db.database import Database
from sqlalchemy import inspect, text

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def test_database_applies_sqlite_connection_settings(tmp_path: Path) -> None:
    """Every application connection applies the required SQLite PRAGMAs."""
    database = Database(tmp_path / "database.db")
    try:
        with database.engine.connect() as connection:
            assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
            assert connection.execute(text("PRAGMA journal_mode")).scalar_one() == "wal"
            assert connection.execute(text("PRAGMA busy_timeout")).scalar_one() == 5000
            assert connection.execute(text("SELECT 1")).scalar_one() == 1
    finally:
        database.dispose()


def test_database_session_rolls_back_uncommitted_work(tmp_path: Path) -> None:
    """Closing the dependency generator rolls back and returns its connection."""
    database = Database(tmp_path / "database.db")
    try:
        with database.engine.begin() as connection:
            connection.execute(text("CREATE TABLE session_probe (value INTEGER NOT NULL)"))

        dependency = database.session()
        session = next(dependency)
        session.execute(text("INSERT INTO session_probe (value) VALUES (1)"))
        dependency.close()

        with database.engine.connect() as connection:
            row_count = connection.execute(text("SELECT COUNT(*) FROM session_probe")).scalar_one()
        assert row_count == 0
    finally:
        database.dispose()


def test_initial_migration_creates_v1_tables(tmp_path: Path) -> None:
    """The Alembic head revision upgrades a completely empty SQLite file."""
    database_path = tmp_path / "migrated.db"
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    config.attributes["database_path"] = database_path

    command.upgrade(config, "head")

    database = Database(database_path)
    try:
        table_names = set(inspect(database.engine).get_table_names())
        assert {
            "alembic_version",
            "threads",
            "messages",
            "runs",
            "tool_calls",
            "files",
            "sources",
        } <= table_names
        run_indexes = {index["name"] for index in inspect(database.engine).get_indexes("runs")}
        assert "uq_runs_active_thread" in run_indexes
        with database.engine.connect() as connection:
            revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            assert revision == "20260731_0001"
    finally:
        database.dispose()
