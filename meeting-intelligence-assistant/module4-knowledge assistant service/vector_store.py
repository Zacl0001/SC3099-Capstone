import config
from llama_index.core.vector_stores import SimpleVectorStore
from llama_index.vector_stores.postgres import PGVectorStore

def create_vector_store():
    if config.VECTOR_STORE_TYPE == "simple":
        return create_simple_vector_store()

    if config.VECTOR_STORE_TYPE == "postgres":
        return create_postgres_vector_store()

def create_simple_vector_store() -> SimpleVectorStore:
    return SimpleVectorStore()

def create_postgres_vector_store() ->  PGVectorStore:
    return PGVectorStore.from_params(
        host=config.POSTGRES_HOST,
        port=config.POSTGRES_PORT,
        user=config.POSTGRES_USER,
        password=config.POSTGRES_PASSWORD,
        database=config.POSTGRES_DB,
        table_name=config.POSTGRES_TABLE_NAME,
        embed_dim=config.POSTGRES_EMBEDDING_DIM
    )