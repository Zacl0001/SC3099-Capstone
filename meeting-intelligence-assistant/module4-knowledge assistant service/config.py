import os

# EMBEDDING MODEL TUNING
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "nomic-embed-text")

# VECTOR STORE
# "simple" = in-process in-memory store (no Docker; data is lost on restart)
# "postgres" = persistent pgvector store (see module2-backend/README.md)
VECTOR_STORE_TYPE = os.environ.get("VECTOR_STORE_TYPE", "postgres").lower()
if VECTOR_STORE_TYPE in {"in-memory", "memory"}:
    VECTOR_STORE_TYPE = "simple"

# POSTGRES
POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "127.0.0.1")
POSTGRES_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.environ.get("POSTGRES_DB", "meeting_intelligence")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "meeting_app")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "meeting_local_dev")
POSTGRES_TABLE_NAME = os.environ.get("POSTGRES_TABLE_NAME", "meeting_chunks")
# Must match the embedding model's dimension (768 for nomic-embed-text).
POSTGRES_EMBEDDING_DIM = int(os.environ.get("POSTGRES_EMBEDDING_DIM", "768"))
