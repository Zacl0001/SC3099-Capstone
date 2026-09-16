import config
from llama_index.embeddings.ollama import OllamaEmbedding

def get_embedding_model() -> OllamaEmbedding:
    """
    Returns an instance of the OllamaEmbedding model.
    """
    return OllamaEmbedding(model_name=config.EMBEDDING_MODEL)
