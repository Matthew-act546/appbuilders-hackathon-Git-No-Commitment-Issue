"""Guarded bootstrap and explicit data-preserving migrations; no resets."""
from functools import lru_cache
from contextlib import closing, contextmanager
import sqlite3

from sqlalchemy import Engine, select
from sqlalchemy.schema import CreateIndex, CreateTable
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from .database import Base
from .errors import QuestError
from .models import CheckIn, GenerationIntent, Profile, Questline, PlanVersion
from .services.quests import utc_text, verify_database

SCHEMA_VERSION = 4
V2_TABLES = {"check_ins", "generation_intents"}
CATALOG_SQL = "SELECT type, name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"


def normalize_catalog(rows) -> tuple:
    # SQLite quotes the rebuilt table name after RENAME; its schema is otherwise
    # identical to fresh SQLAlchemy DDL. Normalize this one known spelling only.
    return tuple((kind, name, " ".join(sql.replace('CREATE TABLE "plan_versions"', 'CREATE TABLE plan_versions').split()) if sql else None)
                 for kind, name, sql in rows)


@lru_cache(maxsize=4)
def expected_catalog(version: int = SCHEMA_VERSION) -> tuple:
    # Compare columns, checks, FKs and indexes, not just a claimed user_version.
    from sqlalchemy.dialects.sqlite import dialect

    with closing(sqlite3.connect(":memory:")) as reference:
        for table in Base.metadata.tables.values():
            if version == 1 and table.name in V2_TABLES:
                continue
            ddl = str(CreateTable(table).compile(dialect=dialect()))
            if version < 4 and table.name == "quests":
                ddl = ddl.replace("\tcompletion_encouragement VARCHAR, \n", "")
            if version < 3 and table.name == "plan_versions":
                ddl = ddl.replace("generated_quest_count<=6", "generated_quest_count<=5").replace("generated_quest_count>=2", "generated_quest_count>=3")
            reference.execute(ddl)
        for table in Base.metadata.tables.values():
            if version == 1 and table.name in V2_TABLES:
                continue
            for index in table.indexes:
                reference.execute(str(CreateIndex(index).compile(dialect=dialect())))
        return normalize_catalog(reference.execute(CATALOG_SQL))


def migrate_v1_to_v2(session) -> None:
    """Run only against the exact v1 catalog inside the bootstrap write unit."""
    connection = session.connection()
    if normalize_catalog(connection.exec_driver_sql(CATALOG_SQL)) != expected_catalog(1):
        raise QuestError("STORAGE_UNAVAILABLE", 503, "Version-one schema mismatch. Preserve the file for review.")
    # Full ORM integrity verification runs after the entire migration chain, in
    # this same transaction, once all current mapped columns exist.
    for model in (CheckIn, GenerationIntent):
        model.__table__.create(connection)
    connection.exec_driver_sql("PRAGMA user_version=2")


def migrate_v2_to_v3(session) -> None:
    """Rebuild only the known plan-count table, copying every column unchanged.

    SQLite's generalized ALTER procedure requires FK enforcement disabled BEFORE
    the transaction, then a foreign_key_check before commit. No writable_schema.
    """
    from sqlalchemy.dialects.sqlite import dialect
    connection = session.connection()
    if normalize_catalog(connection.exec_driver_sql(CATALOG_SQL)) != expected_catalog(2):
        raise QuestError("STORAGE_UNAVAILABLE", 503, "Version-two schema mismatch. Preserve the file for review.")
    if connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() != 0:
        raise QuestError("STORAGE_UNAVAILABLE", 503, "Migration requires the guarded startup transaction.")
    ddl = str(CreateTable(PlanVersion.__table__).compile(dialect=dialect()))
    connection.exec_driver_sql(ddl.replace("CREATE TABLE plan_versions", "CREATE TABLE plan_versions_v3", 1))
    columns = ", ".join(PlanVersion.__table__.columns.keys())
    connection.exec_driver_sql(f"INSERT INTO plan_versions_v3 ({columns}) SELECT {columns} FROM plan_versions")
    connection.exec_driver_sql("DROP TABLE plan_versions")
    connection.exec_driver_sql("ALTER TABLE plan_versions_v3 RENAME TO plan_versions")
    connection.exec_driver_sql("PRAGMA user_version=3")


def migrate_v3_to_v4(session) -> None:
    """Add optional copy only; preserve every quest, ledger entry and reward."""
    connection = session.connection()
    if normalize_catalog(connection.exec_driver_sql(CATALOG_SQL)) != expected_catalog(3):
        raise QuestError("STORAGE_UNAVAILABLE", 503, "Version-three schema mismatch. Preserve the file for review.")
    connection.exec_driver_sql("ALTER TABLE quests ADD COLUMN completion_encouragement VARCHAR")
    connection.exec_driver_sql("PRAGMA user_version=4")


@contextmanager
def bootstrap_unit(database: Engine):
    """Temporarily disable FKs only for a legacy schema rebuild, then restore.

    DDL/copy/catalog/state/FK checks and version change share BEGIN IMMEDIATE.
    A failure rolls back the original schema and rows before pooling the connection.
    """
    try:
        with database.connect().execution_options(sqlite_write=True) as connection:
            raw = connection.connection.driver_connection
            legacy = raw.execute("PRAGMA user_version").fetchone()[0] in (1, 2)
            if legacy:
                raw.execute("PRAGMA foreign_keys=OFF")
                if raw.execute("PRAGMA foreign_keys").fetchone()[0] != 0:
                    raise QuestError("STORAGE_UNAVAILABLE", 503, "Could not prepare the guarded migration.")
            try:
                with connection.begin():
                    with Session(bind=connection, autoflush=False, expire_on_commit=False) as session:
                        yield session
                        session.flush()
            finally:
                try:
                    raw.execute("PRAGMA foreign_keys=ON")
                    restored = raw.execute("PRAGMA foreign_keys").fetchone()[0] == 1
                except sqlite3.Error:
                    restored = False
                if not restored:
                    connection.invalidate()
                    raise QuestError("STORAGE_UNAVAILABLE", 503, "SQLite foreign-key enforcement could not be restored.")
    except OperationalError as exc:
        busy = "locked" in str(exc.orig).lower() or "busy" in str(exc.orig).lower()
        raise QuestError("STORAGE_BUSY" if busy else "STORAGE_UNAVAILABLE", 503, "Local storage could not complete startup. Preserve the database and retry.", True) from None
    except (SQLAlchemyError, sqlite3.Error):
        raise QuestError("STORAGE_UNAVAILABLE", 503, "Local storage could not complete startup. Preserve the database for review.", True) from None


def initialize_database(database: Engine) -> None:
    with bootstrap_unit(database) as session:
        connection = session.connection()
        version = connection.exec_driver_sql("PRAGMA user_version").scalar_one()
        actual = normalize_catalog(connection.exec_driver_sql(CATALOG_SQL))
        if version == 0 and not actual:
            Base.metadata.create_all(connection)
            now = utc_text()
            session.add(Profile(id=1, total_xp=0, created_at=now, updated_at=now))
            session.flush()
            connection.exec_driver_sql(f"PRAGMA user_version={SCHEMA_VERSION}")
        elif version == 1:
            migrate_v1_to_v2(session)
            migrate_v2_to_v3(session)
            migrate_v3_to_v4(session)
        elif version == 2:
            migrate_v2_to_v3(session)
            migrate_v3_to_v4(session)
        elif version == 3:
            migrate_v3_to_v4(session)
        elif version != SCHEMA_VERSION or actual != expected_catalog():
            raise QuestError("STORAGE_UNAVAILABLE", 503,
                             "Unsupported or incomplete database schema. Preserve the file and use a reviewed migration or a new database path.")
        if normalize_catalog(connection.exec_driver_sql(CATALOG_SQL)) != expected_catalog():
            raise QuestError("STORAGE_UNAVAILABLE", 503, "Database schema verification failed.")
        if connection.exec_driver_sql("PRAGMA foreign_key_check").first():
            raise QuestError("STORAGE_UNAVAILABLE", 503, "Database foreign keys are inconsistent. Restore a verified backup.")
        verify_database(session)
        for check_in in session.scalars(select(CheckIn)):
            if check_in.questline_id:
                line = session.get(Questline, check_in.questline_id)
                if line is None or line.goal != check_in.goal:
                    raise QuestError("STORAGE_UNAVAILABLE", 503, "Check-in history is inconsistent.")
        for intent in session.scalars(select(GenerationIntent)):
            model = CheckIn if intent.operation.startswith("check_in_") else Questline
            if intent.state == "succeeded" and session.get(model, intent.resource_id) is None:
                raise QuestError("STORAGE_UNAVAILABLE", 503, "Saved intent history is inconsistent.")
    # journal_mode must be set outside a transaction. No DDL is run on valid restarts.
    try:
        with database.raw_connection() as raw:
            mode = raw.execute("PRAGMA journal_mode=WAL").fetchone()[0]
            if mode not in ("wal", "memory"):
                raise QuestError("STORAGE_UNAVAILABLE", 503, "SQLite WAL mode is unavailable.")
    except sqlite3.Error:
        raise QuestError("STORAGE_UNAVAILABLE", 503, "SQLite journal configuration failed.") from None
