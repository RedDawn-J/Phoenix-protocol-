from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

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


@pytest.mark.asyncio
async def test_sqlite_updates_are_atomic_under_concurrency(tmp_path):
    import asyncio

    client = SQLiteClient(tmp_path / "concurrent.db")
    collection = client.db.counters
    await collection.insert_one({"_id": "global", "value": 0})

    await asyncio.gather(*[
        collection.update_one({"_id": "global"}, {"$inc": {"value": 1}})
        for _ in range(80)
    ])

    result = await collection.find_one({"_id": "global"})
    assert result["value"] == 80
    client.close()


@pytest.mark.asyncio
async def test_sqlite_query_operators_nested_fields_and_projection(tmp_path):
    client = SQLiteClient(tmp_path / "queries.db")
    collection = client.db.events
    await collection.insert_many([
        {"_id": "a", "user_id": "u1", "meta": {"state": "ready"}, "ts": 10},
        {"_id": "b", "user_id": "u2", "meta": {"state": "queued"}, "ts": 20},
        {"_id": "c", "user_id": "u1", "ts": 30},
    ])

    rows = await collection.find({
        "$or": [
            {"meta.state": "ready"},
            {"meta.state": {"$exists": False}},
        ],
        "user_id": {"$in": ["u1"]},
        "ts": {"$gte": 10, "$lte": 30},
    }, {"_id": 0, "user_id": 1, "meta.state": 1}).to_list(10)

    assert len(rows) == 2
    assert all(row["user_id"] == "u1" for row in rows)
    assert {row.get("meta", {}).get("state") for row in rows} == {"ready", None}
    client.close()


@pytest.mark.asyncio
async def test_sqlite_update_many_push_unset_and_aggregate(tmp_path):
    client = SQLiteClient(tmp_path / "updates.db")
    collection = client.db.jobs
    await collection.insert_many([
        {"_id": "1", "status": "pending", "team": "a", "attempts": 0},
        {"_id": "2", "status": "pending", "team": "a", "attempts": 1},
        {"_id": "3", "status": "done", "team": "b", "attempts": 4},
    ])

    changed = await collection.update_many(
        {"status": "pending"},
        {"$set": {"status": "queued"}, "$inc": {"attempts": 1},
         "$push": {"history": {"$each": ["queued"]}}},
    )
    assert changed.matched_count == 2
    assert changed.modified_count == 2

    await collection.update_one({"_id": "1"}, {"$unset": {"history": ""}})
    groups = collection.aggregate([
        {"$match": {"status": "queued"}},
        {"$group": {"_id": "$team", "count": {"$sum": 1}, "attempts": {"$sum": "$attempts"}}},
        {"$sort": [("count", -1)]},
    ]).to_list(10)

    assert groups == [{"_id": "a", "count": 2, "attempts": 3}]
    client.close()


@pytest.mark.asyncio
async def test_sqlite_index_creation_is_real_and_validated(tmp_path):
    client = SQLiteClient(tmp_path / "indexes.db")
    collection = client.db.events
    index_name = await collection.create_index([("user_id", 1), ("ts", -1)])
    indexes = client.db.conn.execute("PRAGMA index_list(documents)").fetchall()
    assert any(row["name"] == index_name for row in indexes)

    with pytest.raises(ValueError, match="Unsupported index field"):
        await collection.create_index([("user_id); DROP TABLE documents;--", 1)])
    client.close()
