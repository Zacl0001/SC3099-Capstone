import config
from llama_index.core.vector_stores import SimpleVectorStore

def create_vector_store():
    if config.VECTOR_STORE_TYPE == "simple":
        return create_simple_vector_store()

    ##TODO: add postgres implementation here in the future


def create_simple_vector_store() -> SimpleVectorStore:
    return SimpleVectorStore()