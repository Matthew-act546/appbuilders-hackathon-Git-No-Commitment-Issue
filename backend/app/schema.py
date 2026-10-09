"""Version-one bootstrap only; unknown schemas are never reset or migrated."""
from functools import lru_cache
from contextlib import closing
import sqlite3

from sqlalchemy import Engine
from sqlalchemy.schema import CreateIndex, CreateTable

from .database import Base, unit_of_work
from .errors import QuestError
from .models import Profile
from .services.quests import utc_text, verify_database

SCHEMA_VERSION = 1
CATALOG_SQL = "SELECT type, name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"


def normalize_catalog(rows) -> tuple:
    return tuple((kind, name, " ".join(sql.split()) if sql else None) for kind, name, sql in rows)


@lru_cache(maxsize=1)
def expected_catalog() -> tuple:
    # Compare columns, checks, FKs and indexes, not just a claimed user_version.
    from sqlalchemy.dialects.sqlite import dialect

    with closing(sqlite3.connect(":memory:")) as reference:
        for table in Base.metadata.tables.values():
            reference.execute(str(CreateTable(table).compile(dialect=dialect())))
        for table in Base.metadata.tables.values():
            for index in table.indexes:
                reference.execute(str(CreateIndex(index).compile(dialect=dialect())))
        return normalize_catalog(reference.execute(CATALOG_SQL))


def initialize_database(database: Engine) -> None:
    with unit_of_work(database, write=True) as session:
        connection = session.connection()
        version = connection.exec_driver_sql("PRAGMA user_version").scalar_one()
        actual = normalize_catalog(connection.exec_driver_sql(CATALOG_SQL))
        if version == 0 and not actual:
            Base.metadata.create_all(connection)
            now = utc_text()
            session.add(Profile(id=1, total_xp=0, created_at=now, updated_at=now))
            session.flush()
            connection.exec_driver_sql(f"PRAGMA user_version={SCHEMA_VERSION}")
        elif version != SCHEMA_VERSION or actual != expected_catalog():
            raise QuestError("STORAGE_UNAVAILABLE", 503,
                             "Unsupported or incomplete database schema. Preserve the file and use a reviewed migration or a new database path.")
        if connection.exec_driver_sql("PRAGMA foreign_key_check").first():
            raise QuestError("STORAGE_UNAVAILABLE", 503, "Database foreign keys are inconsistent. Restore a verified backup.")
        verify_database(session)
    # journal_mode must be set outside a transaction. No DDL is run on valid restarts.
    try:
        with database.raw_connection() as raw:
            mode = raw.execute("PRAGMA journal_mode=WAL").fetchone()[0]
            if mode not in ("wal", "memory"):
                raise QuestError("STORAGE_UNAVAILABLE", 503, "SQLite WAL mode is unavailable.")
    except sqlite3.Error:
        raise QuestError("STORAGE_UNAVAILABLE", 503, "SQLite journal configuration failed.") from None
