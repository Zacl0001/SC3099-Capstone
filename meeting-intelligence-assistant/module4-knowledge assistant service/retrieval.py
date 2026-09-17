from llama_index.core import VectorStoreIndex


def create_retriever(
    index: VectorStoreIndex,
    similarity_top_k: int = 5,
):
    """
    Create a retriever for the given vector index.

    Args:
        index: VectorStoreIndex containing the meeting embeddings.
        similarity_top_k: Number of relevant chunks to retrieve.

    Returns:
        A LlamaIndex retriever.
    """

    return index.as_retriever(
        similarity_top_k=similarity_top_k
    )


def retrieve(
    query: str,
    index: VectorStoreIndex,
    similarity_top_k: int = 5,
):
    """
    Retrieve the most relevant transcript chunks for a query.

    Flow:
        Query
        -> Query embedding
        -> Vector similarity search
        -> Relevant nodes
    """

    retriever = create_retriever(
        index,
        similarity_top_k=similarity_top_k,
    )

    return retriever.retrieve(query)
