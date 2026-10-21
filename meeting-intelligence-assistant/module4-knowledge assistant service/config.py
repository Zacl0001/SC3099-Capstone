#EMBEDDING MODEL TUNING
EMBEDDING_MODEL = "nomic-embed-text"

#VECTOR STORE
VECTOR_STORE_TYPE = "postgres"  # Options: "in-memory", "postgres"

#POSTGRES
# POSTGRES_HOST="localhost"
# POSTGRES_PORT=5433
# POSTGRES_DB="kas"
# POSTGRES_USER="kas"
# POSTGRES_PASSWORD="kas_password"
POSTGRES_HOST = "127.0.0.1"
POSTGRES_PORT = 5432
POSTGRES_DB = "meeting_intelligence"
POSTGRES_USER = "meeting_app"
POSTGRES_PASSWORD = "meeting_local_dev"
POSTGRES_TABLE_NAME="meeting_chunks"
POSTGRES_EMBEDDING_DIM=768 #set this to the dimension of our embedding model, e.g., 768 for "nomic-embed-text"