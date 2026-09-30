#EMBEDDING MODEL TUNING
EMBEDDING_MODEL = "nomic-embed-text"

#VECTOR STORE
VECTOR_STORE_TYPE = "postgres"  # Options: "in-memory", "postgres"

#POSTGRES
POSTGRES_HOST="localhost"
POSTGRES_PORT=5433
POSTGRES_DB="kas"
POSTGRES_USER="kas"
POSTGRES_PASSWORD="kas_password"
POSTGRES_TABLE_NAME="meeting_chunks"
POSTGRES_EMBEDDING_DIM=768 #set this to the dimension of our embedding model, e.g., 768 for "nomic-embed-text"