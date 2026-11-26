"""Transactional, checksum-verified SQLite schema migration runner."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence


class MigrationError(RuntimeError):
    """Raised when the stored database schema cannot be safely advanced."""


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    statements: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.version, int) or self.version < 1:
            raise MigrationError("Migration version must be a positive integer")
        if not isinstance(self.name, str) or not self.name.strip():
            raise MigrationError("Migration name must be a non-empty string")
        immutable_statements = tuple(self.statements)
        if not immutable_statements or any(not isinstance(item, str) or not item.strip() for item in immutable_statements):
            raise MigrationError("Migrations must contain non-empty SQL statements")
        object.__setattr__(self, "statements", immutable_statements)

    @property
    def checksum(self) -> str:
        payload = json.dumps(self.statements, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def apply_migrations(
    connection: sqlite3.Connection,
    migrations: Sequence[Migration] | None = None,
) -> int:
    """Apply pending migrations atomically and return the current schema version.

    Existing pre-migration databases are supported: migration 1 uses
    CREATE TABLE IF NOT EXISTS, so existing documents remain intact.
    Applied migration checksums are immutable. Unknown future versions and
    checksum drift fail closed rather than silently corrupting user data.
    """
    from .versions import MIGRATIONS

    selected = tuple(MIGRATIONS if migrations is None else migrations)
    versions = [migration.version for migration in selected]
    if versions != sorted(set(versions)) or (versions and versions[0] != 1):
        raise MigrationError("Migration versions must be unique, ascending, and start at 1")
    if versions and versions != list(range(1, versions[-1] + 1)):
        raise MigrationError("Migration version sequence contains a gap")
    names = [migration.name for migration in selected]
    if len(names) != len(set(names)):
        raise MigrationError("Migration names must be unique")

    connection.execute(
        """CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            checksum TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )"""
    )
    connection.commit()
    rows = connection.execute(
        "SELECT version, name, checksum FROM schema_migrations ORDER BY version"
    ).fetchall()
    applied = {int(row[0]): (str(row[1]), str(row[2])) for row in rows}
    latest_known = versions[-1] if versions else 0
    future = sorted(version for version in applied if version > latest_known)
    if future:
        raise MigrationError(
            f"Database schema {future[-1]} is newer than this Phoenix build ({latest_known})"
        )
    stored_versions = sorted(applied)
    if stored_versions and stored_versions != list(range(1, stored_versions[-1] + 1)):
        raise MigrationError("Stored migration history contains a version gap")

    for migration in selected:
        previous = applied.get(migration.version)
        if previous:
            if previous != (migration.name, migration.checksum):
                raise MigrationError(
                    f"Applied migration {migration.version} ({migration.name}) does not match its recorded checksum"
                )
            continue

        connection.execute("BEGIN IMMEDIATE")
        try:
            for statement in migration.statements:
                connection.execute(statement)
            connection.execute(
                "INSERT INTO schema_migrations(version, name, checksum, applied_at) VALUES (?, ?, ?, ?)",
                (migration.version, migration.name, migration.checksum, _utc_now()),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    return versions[-1] if versions else 0
