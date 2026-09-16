from llama_index.core import Document
from llama_index.core.node_parser import SemanticSplitterNodeParser

from embedding import get_embedding_model


def create_chunker() -> SemanticSplitterNodeParser:
    #TODO: tune breakpoint_percentile_threshold
    return SemanticSplitterNodeParser(
        embed_model=get_embedding_model()
    )


def chunk_document(document: Document) -> list:
    splitter = create_chunker()
    return splitter.get_nodes_from_documents([document], show_progress=True)