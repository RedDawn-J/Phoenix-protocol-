"""Immutable migration definitions shipped with Phoenix."""
from .runner import Migration

MIGRATIONS = (
    Migration(
        version=1,
        name="initial_document_store",
        statements=(
            """CREATE TABLE IF NOT EXISTS documents (
                collection TEXT NOT NULL,
                doc_id TEXT NOT NULL,
                body TEXT NOT NULL,
                PRIMARY KEY (collection, doc_id)
            )""",
            "CREATE INDEX IF NOT EXISTS idx_documents_collection ON documents(collection)",
        ),
    ),
)
