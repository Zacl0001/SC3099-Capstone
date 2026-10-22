import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from llama_index.core import Document
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SemanticSplitterNodeParser
from llama_index.core.schema import BaseNode, TransformComponent


def find_meeting_files(directory: str | Path) -> list[Path]:
    """Return all meeting JSON files in a directory in stable order."""
    directory_path = Path(directory)

    if not directory_path.is_dir():
        raise NotADirectoryError(
            f"Meeting directory does not exist: {directory_path}"
        )

    return sorted(
        path
        for path in directory_path.iterdir()
        if path.is_file() and path.suffix.lower() == ".json"
    )


def load_meeting_json(file_path: str | Path) -> dict:
    """Load meeting data from a JSON file."""
    with Path(file_path).open("r", encoding="utf-8") as file:
        return json.load(file)


def create_document(meeting_data: dict) -> Document:
    """Convert meeting JSON data into a LlamaIndex Document."""
    lines = []
    section_metadata = []

    for section in meeting_data["sections"]:
        timestamp = section.get("timestamp")
        header = section["speaker_name"]
        if timestamp:
            header += f" [{timestamp}]"
        line = f"{header}: {section['text']}"

        section_start = len("\n".join(lines)) + (1 if lines else 0)
        section_metadata.append(
            {
                "section_id": section["section_id"],
                "speaker": section["speaker_name"],
                "timestamp": timestamp,
                "start": section_start,
                "end": section_start + len(line),
            }
        )

        lines.append(line)

    speakers = sorted(
        {section["speaker_name"] for section in meeting_data["sections"]}
    )

    document = Document(
        id_=f"meeting:{meeting_data['meeting_id']}",
        text="\n".join(lines),
        metadata={
            "meeting_id": str(meeting_data["meeting_id"]),
            "title": meeting_data["title"],
            "meeting_date": _isoformat(meeting_data.get("meeting_date")),
            "meeting_start_time": _isoformat(meeting_data.get("meeting_start_time")),
            "speakers": speakers,
            "section_metadata": section_metadata,
        },
    )

    # Keep metadata that is not useful for semantic processing out of the embedding and LLM prompt text.
    document.excluded_embed_metadata_keys = [
        "section_metadata",
        "meeting_start_time",
    ]
    document.excluded_llm_metadata_keys = [
        "section_metadata",
    ]

    return document


def _isoformat(value):
    """Accept both JSON strings and the backend's date/time objects."""
    return value.isoformat() if hasattr(value, "isoformat") else value


class AttachSectionMetadata(TransformComponent):
    """Keep only the transcript sections that overlap each chunk."""

    def __call__(
        self,
        nodes: list[BaseNode],
        **kwargs: Any,
    ) -> list[BaseNode]:
        for node in nodes:
            sections = node.metadata.get("section_metadata", [])
            node_start = node.start_char_idx
            node_end = node.end_char_idx

            if node_start is None or node_end is None:
                node.metadata["section_metadata"] = sections
                continue

            node.metadata["section_metadata"] = [
                section
                for section in sections
                if node_start < section["end"] and node_end > section["start"]
            ]

        return nodes

class RestoreSectionHeaders(TransformComponent):
    """Prepend speaker/timestamp when a chunk starts inside a section."""

    def __call__(
        self,
        nodes: list[BaseNode],
        **kwargs: Any,
    ) -> list[BaseNode]:
        for node in nodes:
            sections = node.metadata.get("section_metadata", [])

            if not sections:
                continue

            node_start = node.start_char_idx

            if node_start is None:
                continue

            # Find the section containing the start of this chunk.
            starting_section = next(
                (
                    section
                    for section in sections
                    if section["start"] <= node_start < section["end"]
                ),
                None,
            )

            if starting_section is None:
                continue

            # If the chunk starts at the beginning of the section,
            # the speaker/timestamp is already present.
            if node_start == starting_section["start"]:
                continue

            header = starting_section["speaker"]
            if starting_section.get("timestamp"):
                header += f" [{starting_section['timestamp']}]"
            header += ": "

            node.text = header + node.text

        return nodes
    
class MeetingIngestor:
    """Ingest meeting transcripts into the configured vector store."""

    def __init__(self, embedding_model, vector_store):
        self.embedding_model = embedding_model
        self.vector_store = vector_store

        self.pipeline = IngestionPipeline(
            transformations=[
                SemanticSplitterNodeParser(
                    embed_model=self.embedding_model,
                ),
                AttachSectionMetadata(),
                RestoreSectionHeaders(),
                self.embedding_model,
            ],
        )

    def ingest_meetings(self, file_paths: Iterable[str | Path]) -> None:
        """Ingest meeting JSON files into the vector store."""
        file_paths = list(file_paths)

        if not file_paths:
            raise ValueError(
                "At least one meeting JSON file is required for ingestion"
            )

        for file_path in file_paths:
            meeting_data = load_meeting_json(file_path)
            self.ingest_transcript(meeting_data)

    def ingest_transcript(self, meeting_data: dict) -> int:
        """Embed first, then replace this meeting's previously indexed chunks.

        Sequential retries do not accumulate duplicates. Replacement is not a
        transaction across the vector store and the backend database.
        """
        if not meeting_data.get("sections"):
            raise ValueError("Transcript must contain at least one section")
        document = create_document(meeting_data)
        nodes = self.pipeline.run(documents=[document])
        if not nodes:
            raise ValueError("Transcript produced no searchable chunks")
        self.vector_store.delete(document.id_)
        self.vector_store.add(nodes)
        return len(nodes)
