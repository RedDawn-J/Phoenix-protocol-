"""Transactional SQLite document-store adapter for the portable profile.

The adapter deliberately implements a documented Mongo-style subset used by
Phoenix routes. Operations are serialized per process and read/modify/write
mutations execute inside BEGIN IMMEDIATE transactions. Unsupported operators
raise UnsupportedQueryError instead of silently returning misleading results.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence


class UnsupportedQueryError(ValueError):
    """A query or aggregation operator is outside the portable contract."""


@dataclass(frozen=True)
class InsertOneResult:
    inserted_id: Any


@dataclass(frozen=True)
class InsertManyResult:
    inserted_ids: tuple[Any, ...]


@dataclass(frozen=True)
class UpdateResult:
    matched_count: int
    modified_count: int
    upserted_id: Any = None


@dataclass(frozen=True)
class DeleteResult:
    deleted_count: int


class Cursor:
    """Materialized cursor compatible with the async iteration used by routes."""

    def __init__(self, docs: Iterable[dict[str, Any]]):
        self._docs = [dict(doc) for doc in docs]

    def sort(self, key_or_list: Any, direction: int | None = None) -> "Cursor":
        fields = key_or_list if isinstance(key_or_list, list) else [(key_or_list, direction or 1)]
        for key, order in reversed(fields):
            self._docs.sort(
                key=lambda doc: _sortable(_get_path(doc, str(key))),
                reverse=int(order) < 0,
            )
        return self

    def limit(self, count: int) -> "Cursor":
        self._docs = self._docs[:max(0, int(count))]
        return self

    def skip(self, count: int) -> "Cursor":
        self._docs = self._docs[max(0, int(count)):]
        return self

    def __iter__(self) -> Iterator[dict[str, Any]]:
        return iter(self._docs)

    def __aiter__(self) -> "Cursor":
        self._iter_index = 0
        return self

    async def __anext__(self) -> dict[str, Any]:
        if self._iter_index >= len(self._docs):
            raise StopAsyncIteration
        item = self._docs[self._iter_index]
        self._iter_index += 1
        return dict(item)

    async def to_list(self, length: int | None = None) -> list[dict[str, Any]]:
        selected = self._docs if length is None else self._docs[:max(0, length)]
        return [dict(item) for item in selected]


class SQLiteCollection:
    def __init__(self, database: "SQLiteDatabase", name: str):
        if not name or not isinstance(name, str):
            raise ValueError("Collection name must be a non-empty string")
        self._database = database
        self.name = name

    @property
    def _conn(self) -> sqlite3.Connection:
        return self._database.conn

    @property
    def _lock(self) -> threading.RLock:
        return self._database.lock

    async def create_index(self, keys: Any, **options: Any) -> str:
        """Create a real SQLite expression index over JSON document fields."""
        fields = keys if isinstance(keys, list) else [(keys, 1)]
        if not fields or any(not isinstance(item, (tuple, list)) or len(item) != 2 for item in fields):
            raise ValueError("Index keys must be a field or a list of (field, direction) pairs")
        expressions = []
        for field, direction in fields:
            field = str(field)
            if not re.fullmatch(r"[A-Za-z0-9_.]+", field):
                raise ValueError(f"Unsupported index field: {field!r}")
            if int(direction) not in (-1, 1):
                raise ValueError("Index direction must be 1 or -1")
            path = "$." + field.replace(".", ".")
            expressions.append(f"json_extract(body, '{path}') {'DESC' if int(direction) < 0 else 'ASC'}")
        unique = "UNIQUE " if options.get("unique") else ""
        identity = hashlib.sha256((self.name + "|" + "|".join(expressions)).encode()).hexdigest()[:16]
        index_name = "idx_doc_" + identity
        sql = (
            f"CREATE {unique}INDEX IF NOT EXISTS {index_name} "
            f"ON documents(collection, {', '.join(expressions)})"
        )
        await asyncio.to_thread(self._execute_ddl, sql)
        return index_name

    def _execute_ddl(self, sql: str) -> None:
        with self._lock:
            self._conn.execute(sql)
            self._conn.commit()

    async def insert_one(self, doc: dict[str, Any]) -> InsertOneResult:
        if not isinstance(doc, dict):
            raise TypeError("Document must be a dictionary")
        stored = dict(doc)
        stored.setdefault("_id", uuid.uuid4().hex)
        await asyncio.to_thread(self._insert_sync, stored)
        return InsertOneResult(stored["_id"])

    def _insert_sync(self, doc: dict[str, Any]) -> None:
        body = json.dumps(doc, ensure_ascii=False, separators=(",", ":"), default=str)
        with self._lock:
            with self._conn:
                self._conn.execute(
                    "INSERT INTO documents(collection, doc_id, body) VALUES (?, ?, ?)",
                    (self.name, str(doc["_id"]), body),
                )

    async def insert_many(self, docs: Sequence[dict[str, Any]], ordered: bool = True) -> InsertManyResult:
        if not docs:
            return InsertManyResult(())
        prepared = []
        for item in docs:
            if not isinstance(item, dict):
                raise TypeError("Every inserted document must be a dictionary")
            doc = dict(item)
            doc.setdefault("_id", uuid.uuid4().hex)
            prepared.append(doc)
        inserted: list[Any] = []
        def write() -> None:
            with self._lock:
                with self._conn:
                    for doc in prepared:
                        try:
                            self._conn.execute(
                                "INSERT INTO documents(collection, doc_id, body) VALUES (?, ?, ?)",
                                (self.name, str(doc["_id"]), json.dumps(doc, ensure_ascii=False, separators=(",", ":"), default=str)),
                            )
                            inserted.append(doc["_id"])
                        except sqlite3.IntegrityError:
                            if ordered:
                                raise
        await asyncio.to_thread(write)
        return InsertManyResult(tuple(inserted))

    async def find_one(
        self,
        filt: dict[str, Any] | None = None,
        projection: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        docs = await asyncio.to_thread(self._all_sync)
        matched = [doc for doc in docs if _matches(doc, filt or {})]
        if kwargs.get("sort"):
            Cursor(matched).sort(kwargs["sort"])
            matched = Cursor(matched).sort(kwargs["sort"])._docs
        return _project(matched[0], projection) if matched else None

    def find(
        self,
        filt: dict[str, Any] | None = None,
        projection: dict[str, Any] | None = None,
    ) -> Cursor:
        return Cursor(
            _project(doc, projection)
            for doc in self._all_sync()
            if _matches(doc, filt or {})
        )

    async def count_documents(self, filt: dict[str, Any] | None = None) -> int:
        docs = await asyncio.to_thread(self._all_sync)
        return sum(1 for doc in docs if _matches(doc, filt or {}))

    async def distinct(self, key: str, filt: dict[str, Any] | None = None) -> list[Any]:
        docs = await asyncio.to_thread(self._all_sync)
        values: list[Any] = []
        for doc in docs:
            if _matches(doc, filt or {}):
                value = _get_path(doc, key)
                candidates = value if isinstance(value, list) else [value]
                for candidate in candidates:
                    if candidate is not _MISSING and candidate not in values:
                        values.append(candidate)
        return values

    async def update_one(
        self,
        filt: dict[str, Any],
        update: dict[str, Any],
        upsert: bool = False,
    ) -> UpdateResult:
        return await asyncio.to_thread(self._update_sync, filt, update, upsert, False)

    async def update_many(
        self,
        filt: dict[str, Any],
        update: dict[str, Any],
        upsert: bool = False,
    ) -> UpdateResult:
        return await asyncio.to_thread(self._update_sync, filt, update, upsert, True)

    def _update_sync(
        self,
        filt: dict[str, Any],
        update: dict[str, Any],
        upsert: bool,
        many: bool,
    ) -> UpdateResult:
        matched = modified = 0
        upserted_id = None
        with self._lock:
            with self._conn:
                rows = self._conn.execute(
                    "SELECT doc_id, body FROM documents WHERE collection = ?",
                    (self.name,),
                ).fetchall()
                for doc_id, body in rows:
                    doc = json.loads(body)
                    if not _matches(doc, filt):
                        continue
                    matched += 1
                    changed = _apply_update(doc, update, inserting=False)
                    if changed:
                        self._conn.execute(
                            "UPDATE documents SET body = ? WHERE collection = ? AND doc_id = ?",
                            (json.dumps(doc, ensure_ascii=False, separators=(",", ":"), default=str), self.name, doc_id),
                        )
                        modified += 1
                    if not many:
                        break
                if matched == 0 and upsert:
                    seed = {key: value for key, value in filt.items() if not key.startswith("$") and not isinstance(value, dict)}
                    seed.setdefault("_id", uuid.uuid4().hex)
                    _apply_update(seed, update, inserting=True)
                    self._conn.execute(
                        "INSERT INTO documents(collection, doc_id, body) VALUES (?, ?, ?)",
                        (self.name, str(seed["_id"]), json.dumps(seed, ensure_ascii=False, separators=(",", ":"), default=str)),
                    )
                    upserted_id = seed["_id"]
        return UpdateResult(matched, modified, upserted_id)

    async def delete_one(self, filt: dict[str, Any]) -> DeleteResult:
        return await asyncio.to_thread(self._delete_sync, filt, False)

    async def delete_many(self, filt: dict[str, Any]) -> DeleteResult:
        return await asyncio.to_thread(self._delete_sync, filt, True)

    def _delete_sync(self, filt: dict[str, Any], many: bool) -> DeleteResult:
        deleted = 0
        with self._lock:
            with self._conn:
                rows = self._conn.execute(
                    "SELECT doc_id, body FROM documents WHERE collection = ?",
                    (self.name,),
                ).fetchall()
                for doc_id, body in rows:
                    if _matches(json.loads(body), filt):
                        self._conn.execute(
                            "DELETE FROM documents WHERE collection = ? AND doc_id = ?",
                            (self.name, doc_id),
                        )
                        deleted += 1
                        if not many:
                            break
        return DeleteResult(deleted)

    def _all_sync(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT body FROM documents WHERE collection = ?",
                (self.name,),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def aggregate(self, pipeline: Sequence[dict[str, Any]]) -> Cursor:
        docs = self._all_sync()
        for stage in pipeline:
            if len(stage) != 1:
                raise UnsupportedQueryError("Each aggregation stage must contain exactly one operator")
            operator, spec = next(iter(stage.items()))
            if operator == "$match":
                docs = [doc for doc in docs if _matches(doc, spec)]
            elif operator == "$sort":
                docs = Cursor(docs).sort(list(spec.items()))._docs
            elif operator == "$limit":
                docs = docs[:max(0, int(spec))]
            elif operator == "$skip":
                docs = docs[max(0, int(spec)):]
            elif operator == "$project":
                docs = [_project(doc, spec) for doc in docs]
            elif operator == "$count":
                docs = [{str(spec): len(docs)}]
            elif operator == "$group":
                docs = _group_documents(docs, spec)
            else:
                raise UnsupportedQueryError(f"Unsupported aggregation stage: {operator}")
        return Cursor(docs)


class SQLiteDatabase:
    def __init__(self, path: Path):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(self.path, timeout=10.0, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA busy_timeout = 10000")
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.execute("PRAGMA synchronous = FULL")
        from migrations import apply_migrations
        apply_migrations(self.conn)
        self._closed = False

    def __getattr__(self, name: str) -> SQLiteCollection:
        if name.startswith("_"):
            raise AttributeError(name)
        return SQLiteCollection(self, name)

    def __getitem__(self, name: str) -> SQLiteCollection:
        return SQLiteCollection(self, name)

    def close(self) -> None:
        with self.lock:
            if not self._closed:
                self.conn.close()
                self._closed = True


class SQLiteClient:
    def __init__(self, path: Path):
        self.db = SQLiteDatabase(path)

    def __getitem__(self, _name: str) -> SQLiteDatabase:
        return self.db

    def close(self) -> None:
        self.db.close()


_MISSING = object()


def _get_path(document: dict[str, Any], path: str) -> Any:
    current: Any = document
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return _MISSING
        current = current[part]
    return current


def _set_path(document: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    target = document
    for part in parts[:-1]:
        child = target.get(part)
        if not isinstance(child, dict):
            child = {}
            target[part] = child
        target = child
    target[parts[-1]] = value


def _unset_path(document: dict[str, Any], path: str) -> None:
    parts = path.split(".")
    target = document
    for part in parts[:-1]:
        target = target.get(part)
        if not isinstance(target, dict):
            return
    target.pop(parts[-1], None)


def _compare(actual: Any, expected: Any, operator: str) -> bool:
    if actual is _MISSING:
        return operator == "$ne" and actual != expected
    if operator == "$eq":
        return actual == expected
    if operator == "$ne":
        return actual != expected
    if operator == "$in":
        return actual in expected or (isinstance(actual, list) and any(item in expected for item in actual))
    if operator == "$nin":
        return actual not in expected
    if operator == "$exists":
        return bool(expected)
    if operator in {"$gt", "$gte", "$lt", "$lte"}:
        if actual is None:
            return False
        try:
            return {
                "$gt": lambda: actual > expected,
                "$gte": lambda: actual >= expected,
                "$lt": lambda: actual < expected,
                "$lte": lambda: actual <= expected,
            }[operator]()
        except TypeError:
            left, right = str(actual), str(expected)
            return {
                "$gt": lambda: left > right,
                "$gte": lambda: left >= right,
                "$lt": lambda: left < right,
                "$lte": lambda: left <= right,
            }[operator]()
    if operator == "$regex":
        return bool(re.search(str(expected), str(actual), re.I))
    if operator == "$options":
        return True
    raise UnsupportedQueryError(f"Unsupported query operator: {operator}")


def _matches(document: dict[str, Any], filt: dict[str, Any]) -> bool:
    for key, expected in filt.items():
        if key == "$or":
            if not isinstance(expected, list) or not any(_matches(document, item) for item in expected):
                return False
            continue
        if key == "$and":
            if not isinstance(expected, list) or not all(_matches(document, item) for item in expected):
                return False
            continue
        if key == "$nor":
            if not isinstance(expected, list) or any(_matches(document, item) for item in expected):
                return False
            continue
        if key == "$text":
            query = str(expected.get("$search", "")).casefold()
            haystack = json.dumps(document, ensure_ascii=False, default=str).casefold()
            if not query or query not in haystack:
                return False
            continue
        actual = _get_path(document, key)
        if isinstance(expected, dict) and any(str(op).startswith("$") for op in expected):
            for operator, operand in expected.items():
                if operator == "$options":
                    continue
                if operator == "$regex":
                    flags = re.I if expected.get("$options") == "i" else 0
                    if actual is _MISSING or not re.search(str(operand), str(actual), flags):
                        return False
                elif not _compare(actual, operand, operator):
                    return False
        elif expected is None:
            if actual is not _MISSING and actual is not None:
                return False
        elif actual != expected:
            return False
    return True


def _apply_update(document: dict[str, Any], update: dict[str, Any], inserting: bool) -> bool:
    if not isinstance(update, dict):
        raise TypeError("Update must be a dictionary")
    if not any(str(key).startswith("$") for key in update):
        replacement = dict(update)
        replacement.setdefault("_id", document.get("_id", uuid.uuid4().hex))
        changed = replacement != document
        document.clear()
        document.update(replacement)
        return changed
    changed = False
    for operator, values in update.items():
        if not isinstance(values, dict):
            raise UnsupportedQueryError(f"{operator} requires an object")
        if operator == "$set" or (operator == "$setOnInsert" and inserting):
            for key, value in values.items():
                if _get_path(document, key) != value:
                    _set_path(document, key, value)
                    changed = True
        elif operator == "$setOnInsert":
            continue
        elif operator == "$unset":
            for key in values:
                if _get_path(document, key) is not _MISSING:
                    _unset_path(document, key)
                    changed = True
        elif operator == "$inc":
            for key, amount in values.items():
                current = _get_path(document, key)
                current = 0 if current is _MISSING else current
                _set_path(document, key, current + amount)
                changed = True
        elif operator == "$push":
            for key, value in values.items():
                current = _get_path(document, key)
                if current is _MISSING:
                    current = []
                if not isinstance(current, list):
                    raise TypeError(f"$push target {key!r} is not an array")
                additions = value.get("$each", []) if isinstance(value, dict) and "$each" in value else [value]
                current = list(current) + additions
                _set_path(document, key, current)
                changed = True
        elif operator == "$addToSet":
            for key, value in values.items():
                current = _get_path(document, key)
                current = [] if current is _MISSING else list(current)
                additions = value.get("$each", []) if isinstance(value, dict) and "$each" in value else [value]
                for item in additions:
                    if item not in current:
                        current.append(item)
                        changed = True
                _set_path(document, key, current)
        else:
            raise UnsupportedQueryError(f"Unsupported update operator: {operator}")
    return changed


def _project(document: dict[str, Any], projection: dict[str, Any] | None) -> dict[str, Any]:
    if not projection:
        return dict(document)
    included = [key for key, enabled in projection.items() if enabled and key != "_id"]
    excluded = [key for key, enabled in projection.items() if not enabled]
    if included:
        result: dict[str, Any] = {}
        for key in included:
            value = _get_path(document, key)
            if value is not _MISSING:
                _set_path(result, key, value)
        if projection.get("_id", 1) and "_id" in document:
            result["_id"] = document["_id"]
        return result
    result = json.loads(json.dumps(document, default=str))
    for key in excluded:
        _unset_path(result, key)
    return result


def _sortable(value: Any) -> tuple[int, Any]:
    if value is _MISSING or value is None:
        return (0, "")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return (1, float(value))
    return (1, str(value))


def _group_documents(documents: list[dict[str, Any]], spec: dict[str, Any]) -> list[dict[str, Any]]:
    if "_id" not in spec:
        raise UnsupportedQueryError("$group requires an _id expression")
    groups: dict[str, tuple[Any, list[dict[str, Any]]]] = {}
    for doc in documents:
        raw_key = spec["_id"]
        key = _get_path(doc, raw_key[1:]) if isinstance(raw_key, str) and raw_key.startswith("$") else raw_key
        key = None if key is _MISSING else key
        token = json.dumps(key, sort_keys=True, default=str)
        groups.setdefault(token, (key, []))[1].append(doc)
    output = []
    for key, items in groups.values():
        result: dict[str, Any] = {"_id": key}
        for field, expression in spec.items():
            if field == "_id":
                continue
            if not isinstance(expression, dict) or len(expression) != 1:
                raise UnsupportedQueryError(f"Unsupported group accumulator for {field}")
            accumulator, operand = next(iter(expression.items()))
            values = [
                (_get_path(item, operand[1:]) if isinstance(operand, str) and operand.startswith("$") else operand)
                for item in items
            ]
            values = [value for value in values if value is not _MISSING]
            if accumulator == "$sum":
                result[field] = sum((1 if operand == 1 else value or 0) for value in values) if operand != 1 else len(items)
            elif accumulator == "$avg":
                numeric = [value for value in values if isinstance(value, (int, float))]
                result[field] = sum(numeric) / len(numeric) if numeric else None
            elif accumulator == "$min":
                result[field] = min(values) if values else None
            elif accumulator == "$max":
                result[field] = max(values) if values else None
            elif accumulator == "$first":
                result[field] = values[0] if values else None
            elif accumulator == "$last":
                result[field] = values[-1] if values else None
            elif accumulator == "$push":
                result[field] = values
            elif accumulator == "$addToSet":
                result[field] = list(dict.fromkeys(values))
            else:
                raise UnsupportedQueryError(f"Unsupported group accumulator: {accumulator}")
        output.append(result)
    return output
