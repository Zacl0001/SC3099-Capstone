from typing import Any

from llama_index.core import VectorStoreIndex


class MeetingRetriever:
    """Retrieve relevant meeting transcript chunks."""

    def __init__(self, index: VectorStoreIndex, similarity_top_k: int = 5):
        if similarity_top_k < 1:
            raise ValueError("similarity_top_k must be at least 1")

        self.index = index
        self.similarity_top_k = similarity_top_k

    def search(self, query: str) -> dict[str, Any]:
        """Search for relevant meeting transcript chunks based on a query and return the results in JSON format."""

        query = query.strip()

        if not query:
            raise ValueError("Query must not be empty")

        retriever = self.index.as_retriever(
            similarity_top_k=self.similarity_top_k
        )

        nodes = retriever.retrieve(query)

        return {
            "query": query,
            "results": [
                {
                    "text": result.node.text,
                    "score": result.score,
                    "meeting_id": result.node.metadata.get("meeting_id"),
                    "title": result.node.metadata.get("title"),
                    "meeting_date": result.node.metadata.get("meeting_date"),
                    "meeting_start_time": result.node.metadata.get(
                        "meeting_start_time"
                    ),
                    "speakers": result.node.metadata.get("speakers", []),
                    "section_metadata": result.node.metadata.get(
                        "section_metadata", []
                    ),
                }
                for result in nodes
            ],
        }