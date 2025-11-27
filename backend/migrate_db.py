from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

from sqlalchemy import inspect as sa_inspect, text
from sqlalchemy.engine import Connection

from app.db.session import engine

logger = logging.getLogger("db.migrations")


@dataclass(frozen=True)
class Migration:
    """Simple representation of a migration step."""

    id: str
    description: str
    apply: Callable[[Connection], None]


def _ensure_schema_table(conn: Connection) -> None:
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id TEXT PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
            """
        )
    )


def _fetch_applied_migrations(conn: Connection) -> set[str]:
    result = conn.execute(text("SELECT id FROM schema_migrations"))
    return {row[0] for row in result}


def _record_migration(conn: Connection, migration_id: str) -> None:
    conn.execute(
        text("INSERT INTO schema_migrations (id) VALUES (:id)"),
        {"id": migration_id},
    )


def _get_table_info(conn: Connection, table_name: str) -> dict[str, dict[str, object]]:
    dialect_name = conn.dialect.name
    info: dict[str, dict[str, object]] = {}
    if dialect_name == "sqlite":
        result = conn.exec_driver_sql(f"PRAGMA table_info({table_name})")
        for row in result:
            mapping = dict(row._mapping)
            info[str(mapping["name"])] = mapping
        return info

    inspector = sa_inspect(conn)
    for column in inspector.get_columns(table_name):
        info[column["name"]] = {
            "name": column["name"],
            "type": column.get("type"),
            "notnull": 0 if column.get("nullable", True) else 1,
        }
    return info


def _ensure_column(conn: Connection, table: str, column: str, ddl: str) -> None:
    info = _get_table_info(conn, table)
    if column in info:
        return
    logger.info("Adding column %s.%s", table, column)
    conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def _sqlite_make_attachment_data_nullable(conn: Connection) -> None:
    logger.info("Rebuilding message_attachments table to allow NULL data column (SQLite)")
    conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
    try:
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS message_attachments_new (
                id TEXT NOT NULL,
                message_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                content_type TEXT NOT NULL,
                data BLOB,
                storage_filename TEXT,
                size_bytes INTEGER,
                created_at DATETIME NOT NULL,
                PRIMARY KEY (id),
                FOREIGN KEY(message_id) REFERENCES messages (id)
            )
            """
        )
        columns = (
            "id, message_id, filename, content_type, data, storage_filename, size_bytes, created_at"
        )
        conn.exec_driver_sql(
            f"INSERT INTO message_attachments_new ({columns}) SELECT {columns} FROM message_attachments"
        )
        conn.exec_driver_sql("DROP TABLE message_attachments")
        conn.exec_driver_sql("ALTER TABLE message_attachments_new RENAME TO message_attachments")
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_message_attachments_message_id ON message_attachments (message_id)"
        )
    finally:
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")


def _ensure_attachment_data_nullable(conn: Connection, dialect_name: str) -> None:
    table_info = _get_table_info(conn, "message_attachments")
    data_column = table_info.get("data")
    if not data_column:
        logger.warning("message_attachments.data column missing; skipping nullability update")
        return
    if int(data_column.get("notnull", 0)) == 0:
        return
    if dialect_name == "sqlite":
        _sqlite_make_attachment_data_nullable(conn)
    elif dialect_name in {"postgresql", "postgres"}:
        logger.info("Dropping NOT NULL constraint on message_attachments.data (PostgreSQL)")
        conn.exec_driver_sql("ALTER TABLE message_attachments ALTER COLUMN data DROP NOT NULL")
    else:
        logger.warning(
            "Dialect %s is not supported for automatic NOT NULL drop on message_attachments.data",
            dialect_name,
        )


def migration_001_message_attachment_links(conn: Connection) -> None:
    dialect_name = conn.dialect.name
    _ensure_column(conn, "message_attachments", "storage_filename", "TEXT")
    _ensure_column(conn, "message_attachments", "size_bytes", "INTEGER")
    _ensure_attachment_data_nullable(conn, dialect_name)


def migration_002_message_metadata(conn: Connection) -> None:
    _ensure_column(conn, "messages", "metadata", "JSON NOT NULL DEFAULT '{}'")


MIGRATIONS: list[Migration] = [
    Migration(
        id="001_message_attachment_links",
        description="Add storage metadata to message_attachments and allow null binary data",
        apply=migration_001_message_attachment_links,
    ),
    Migration(
        id="002_message_metadata",
        description="Add metadata column to messages for provider data",
        apply=migration_002_message_metadata,
    ),
]


def apply_migrations() -> None:
    logger.info("Starting database migration(s)")
    with engine.begin() as conn:
        _ensure_schema_table(conn)
        applied = _fetch_applied_migrations(conn)
        for migration in MIGRATIONS:
            if migration.id in applied:
                logger.info("Skipping migration %s (already applied)", migration.id)
                continue
            logger.info("Applying migration %s: %s", migration.id, migration.description)
            migration.apply(conn)
            _record_migration(conn, migration.id)
        logger.info("All migrations complete")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    apply_migrations()
