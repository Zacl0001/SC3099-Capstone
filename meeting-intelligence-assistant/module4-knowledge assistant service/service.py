from collections.abc import Iterable
from pathlib import Path
from typing import Any

from llama_index.core import VectorStoreIndex

if __package__:
    from .embedding import get_embedding_model
    from .ingestion import MeetingIngestor
    from .retriever import MeetingRetriever
    from .vector_store import create_vector_store
else:  # Preserve the existing standalone test_kas.py workflow.
    from embedding import get_embedding_model
    from ingestion import MeetingIngestor
    from retriever import MeetingRetriever
    from vector_store import create_vector_store


class KnowledgeAssistant:
    """Main interface for the Knowledge Assistant Service."""

    def __init__(self, similarity_top_k: int = 5):
        embedding_model = get_embedding_model()
        vector_store = create_vector_store()

        self.ingestor = MeetingIngestor(
            embedding_model=embedding_model,
            vector_store=vector_store,
        )

        index = VectorStoreIndex.from_vector_store(
            vector_store,
            embed_model=embedding_model,
        )

        self.retriever = MeetingRetriever(
            index=index,
            similarity_top_k=similarity_top_k,
        )

    def ingest(self, file_paths: Iterable[str | Path]) -> None:
        """Ingest meeting JSON files into the knowledge base."""
        self.ingestor.ingest_meetings(file_paths)

    def search(self, query: str) -> dict[str, Any]:
        """Search the knowledge base for relevant meeting chunks."""
        return self.retriever.search(query)

    def ingest_transcript(self, meeting: dict[str, Any]) -> int:
        """Index a processed backend transcript without an intermediate JSON file."""
        return self.ingestor.ingest_transcript(meeting)

