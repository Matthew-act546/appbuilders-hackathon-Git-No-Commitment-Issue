from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from .config import get_settings

def create_sqlite_engine(url: str) -> Engine:
    if not url.startswith("sqlite:"):
        raise ValueError("Local quest persistence requires a SQLite DATABASE_URL.")
    options = {"poolclass": StaticPool} if url in ("sqlite://", "sqlite:///:memory:") else {}
    result = create_engine(url, connect_args={"check_same_thread": False}, **options)

    @event.listens_for(result, "connect")
    def configure_connection(connection, _record):
        # One transaction strategy on Python 3.11+; SELECT and DDL also transact.
        connection.isolation_level = None
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA synchronous=FULL")
        if cursor.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            raise RuntimeError("SQLite foreign-key enforcement is unavailable.")
        cursor.close()

    @event.listens_for(result, "begin")
    def begin_transaction(connection):
        connection.exec_driver_sql("BEGIN IMMEDIATE" if connection.get_execution_options().get("sqlite_write") else "BEGIN")

    return result


engine = create_sqlite_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_session() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session


@contextmanager
def unit_of_work(database: Engine, *, write: bool = False) -> Generator[Session, None, None]:
    """One snapshot/atomic write; no Session is shared across requests or inference."""
    from .errors import QuestError

    try:
        with database.connect().execution_options(sqlite_write=write) as connection:
            with connection.begin():
                with Session(bind=connection, autoflush=False, expire_on_commit=False) as session:
                    yield session
                    session.flush()
    except OperationalError as exc:
        busy = "locked" in str(exc.orig).lower() or "busy" in str(exc.orig).lower()
        raise QuestError("STORAGE_BUSY" if busy else "STORAGE_UNAVAILABLE", 503,
                         "Local storage is busy. Retry shortly." if busy else "Local storage is unavailable.", True) from None
    except SQLAlchemyError:
        raise QuestError("STORAGE_UNAVAILABLE", 503, "Local storage could not save or read this operation.", True) from None
