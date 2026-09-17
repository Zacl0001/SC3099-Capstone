import json

from llama_index.core import Document, VectorStoreIndex

from chunking import chunk_document
from vector_store import create_vector_store


def load_meeting_json(file_path: str) -> dict:
    """Load meeting data from a JSON file."""
    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)


def create_document(meeting_data: dict) -> Document:
    """Convert meeting JSON data into a LlamaIndex Document."""

    full_transcript_text = "\n".join(
        f"{section['speaker_name']}: {section['text']}"
        for section in meeting_data["sections"]
    )

    return Document(
        text=full_transcript_text,
        metadata={
            "meeting_id": meeting_data["meeting_id"],
            "title": meeting_data["title"],
        },
    )


def ingest_meetings(file_paths: list[str]) -> VectorStoreIndex:
    """Ingest multiple meeting files into one vector index."""

    all_nodes = []

    for file_path in file_paths:
        meeting_data = load_meeting_json(file_path)

        print(f"Ingesting: {file_path}")

        document = create_document(meeting_data)
        nodes = chunk_document(document)

        all_nodes.extend(nodes)

    vector_store = create_vector_store()

    index = VectorStoreIndex(
        all_nodes,
        vector_store=vector_store,
    )

    return index