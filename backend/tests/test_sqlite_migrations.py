from __future__ import annotations

import sqlite3

import pytest

from migrations import Migration, MigrationError, apply_migrations
from sqlite_store import SQLiteClient


def test_fresh_database_applies_initial_schema_and_is_idempotent(tmp_path):
    path = tmp_path / "fresh.db"
    client = SQLiteClient(path)
    version = client.db.conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
    assert version == 1
    client.close()

    reopened = SQLiteClient(path)
    assert reopened.db.conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 1
    reopened.close()


def test_existing_unversioned_document_store_is_preserved(tmp_path):
    path = tmp_path / "legacy.db"
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE documents(collection text not null, doc_id text not null, body text not null, primary key(collection, doc_id))"
    )
    connection.execute(
        "INSERT INTO documents(collection, doc_id, body) VALUES (?, ?, ?)",
        ("projects", "p1", '{"project_id":"p1","name":"Existing"}'),
    )
    connection.commit()
    connection.close()

    client = SQLiteClient(path)
    project = client.db.projects.find_one({"project_id": "p1"})
    assert project["name"] == "Existing"
    assert client.db.conn.execute("SELECT version FROM schema_migrations").fetchone()[0] == 1
    client.close()


def test_applied_migration_checksum_is_immutable(tmp_path):
    connection = sqlite3.connect(tmp_path / "checksum.db")
    apply_migrations(connection)
    changed = (Migration(1, "initial_document_store", ("CREATE TABLE altered (id INTEGER)",)),)
    with pytest.raises(MigrationError, match="checksum"):
        apply_migrations(connection, changed)
    connection.close()


def test_unknown_future_schema_fails_closed(tmp_path):
    connection = sqlite3.connect(tmp_path / "future.db")
    apply_migrations(connection)
    connection.execute(
        "INSERT INTO schema_migrations(version, name, checksum, applied_at) VALUES (99, 'future', 'abc', '2099-01-01T00:00:00Z')"
    )
    connection.commit()
    with pytest.raises(MigrationError, match="newer than this Phoenix build"):
        apply_migrations(connection)
    connection.close()
