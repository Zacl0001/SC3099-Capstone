"""Knowledge Assistant Service (KAS) - HTTP API.

Implements docs/kas_http_api.md on top of this module's own components
(ingestion transforms, embedding model, vector store). Contract between
module3 (consumer, port 8001) and this service (provider, port 8002).

Run (from this folder):
    .venv\\Scripts\\python.exe -m uvicorn app:app --port 8002
"""

from contextlib import asynccontextmanager

import httpx
import ollama
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from llama_index.core import Document, VectorStoreIndex
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SemanticSplitterNodeParser
from llama_index.core.vector_stores import MetadataFilter, MetadataFilters
from pydantic import BaseModel, Field

import config
from embedding import get_embedding_model
from ingestion import (
    AttachSectionMetadata,
    RestoreSectionHeaders,
    create_document,
)
from vector_store import create_vector_store


# --------------------------------------------------------------------------
# Request models
# --------------------------------------------------------------------------


class Section(BaseModel):
    section_id: str
    speaker_name: str
    timestamp: str
    text: str


class IngestRequest(BaseModel):
    meeting_id: str
    title: str = ""
    meeting_date: str = ""
    meeting_start_time: str = ""
    sections: list[Section] = Field(..., min_length=1)


class SearchRequest(BaseModel):
    meeting_id: str
    query: str
    top_k: int = Field(default=5, ge=1, le=20)


class ChunkRequest(BaseModel):
    meeting_id: str | None = None
    transcript: str | None = None
    sections: list[Section] | None = None


# --------------------------------------------------------------------------
# App state (built once at startup)
# --------------------------------------------------------------------------


class AppState:
    embedding_model: object = None
    vector_store: object = None
    index: VectorStoreIndex | None = None
    ingest_pipeline: IngestionPipeline | None = None
    chunk_pipeline: IngestionPipeline | None = None


state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    state.embedding_model = get_embedding_model()
    state.vector_store = create_vector_store()
    state.index = VectorStoreIndex.from_vector_store(
        state.vector_store, embed_model=state.embedding_model
    )
    # Same transformation list as MeetingIngestor: split, attribute, embed, store.
    state.ingest_pipeline = IngestionPipeline(
        transformations=[
            SemanticSplitterNodeParser(embed_model=state.embedding_model),
            AttachSectionMetadata(),
            RestoreSectionHeaders(),
            state.embedding_model,
        ],
        vector_store=state.vector_store,
    )
    # Same, minus embedding/storing: /chunk splits without indexing anything.
    state.chunk_pipeline = IngestionPipeline(
        transformations=[
            SemanticSplitterNodeParser(embed_model=state.embedding_model),
            AttachSectionMetadata(),
            RestoreSectionHeaders(),
        ],
    )
    yield
    await state.embedding_model.aclose() if hasattr(
        state.embedding_model, "aclose"
    ) else None


app = FastAPI(title="Knowledge Assistant Service", lifespan=lifespan)


# Contract: validation errors are 400, not FastAPI's default 422.
@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=400, content={"detail": str(exc.errors())}
    )


# Contract: 503 when the embedding model (Ollama) is unreachable.
_OLLAMA_UNREACHABLE = (httpx.HTTPError, ConnectionError, OSError, TimeoutError)


def _run_pipeline(pipeline: IngestionPipeline, **kwargs) -> list:
    try:
        return pipeline.run(**kwargs)
    except ollama.ResponseError as exc:  # model missing / Ollama HTTP error
        raise HTTPException(
            status_code=503,
            detail=f"embedding model (Ollama) error: {exc}",
        ) from exc
    except _OLLAMA_UNREACHABLE as exc:
        raise HTTPException(
            status_code=503,
            detail="embedding model (Ollama) is unreachable",
        ) from exc


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------


@app.get("/health")
@app.post("/health")
def health() -> dict:
    return {"status": "healthy", "model": config.EMBEDDING_MODEL}


@app.post("/ingest")
def ingest(body: IngestRequest) -> dict:
    """Index one meeting. Idempotent: doc id == meeting_id, so re-ingest
    deletes the previous chunks for that meeting first."""
    meeting = body.model_dump()
    doc = create_document(meeting)
    doc.id_ = body.meeting_id

    if state.index is None:
        raise HTTPException(status_code=503, detail="index not ready")

    try:
        state.index.delete_ref_doc(body.meeting_id, delete_from_store=True)
    except Exception:  # first ingest: nothing to delete
        pass

    nodes = _run_pipeline(state.ingest_pipeline, documents=[doc])
    return {
        "meeting_id": body.meeting_id,
        "status": "ingested",
        "chunks": len(nodes),
    }


@app.post("/search")
def search(body: SearchRequest) -> dict:
    """Top-K semantic search scoped to ONE meeting's chunks."""
    if state.index is None:
        raise HTTPException(status_code=503, detail="index not ready")

    filters = MetadataFilters(
        filters=[
            MetadataFilter(key="meeting_id", value=body.meeting_id),
        ]
    )

    try:
        retriever = state.index.as_retriever(
            similarity_top_k=body.top_k, filters=filters
        )
        nodes = retriever.retrieve(body.query)
    except ollama.ResponseError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"embedding model (Ollama) error: {exc}",
        ) from exc
    except _OLLAMA_UNREACHABLE as exc:
        raise HTTPException(
            status_code=503,
            detail="embedding model (Ollama) is unreachable",
        ) from exc

    results = []
    for hit in nodes:
        metadata = hit.node.metadata
        # Safety net in case the vector store does not push the filter down.
        if metadata.get("meeting_id") != body.meeting_id:
            continue
        results.append(
            {
                "text": hit.node.text,
                "score": float(hit.score or 0.0),
                "meeting_id": metadata.get("meeting_id"),
                "title": metadata.get("title"),
                "meeting_date": metadata.get("meeting_date"),
                "meeting_start_time": metadata.get("meeting_start_time"),
                "speakers": metadata.get("speakers", []),
                "section_metadata": metadata.get("section_metadata", []),
            }
        )

    return {"query": body.query, "results": results}


@app.post("/chunk")
def chunk(body: ChunkRequest) -> dict:
    """Semantic chunking WITHOUT indexing (long-transcript analysis)."""
    if not body.transcript and not body.sections:
        raise HTTPException(
            status_code=400,
            detail="provide 'transcript' or 'sections'",
        )

    if body.sections:
        meeting = {
            "meeting_id": body.meeting_id or "unknown",
            "title": "",
            "meeting_date": "",
            "meeting_start_time": "",
            "sections": [s.model_dump() for s in body.sections],
        }
        doc = create_document(meeting)
    else:
        doc = Document(text=body.transcript or "")

    if not doc.text.strip():
        return {"meeting_id": body.meeting_id, "chunks": []}

    nodes = _run_pipeline(state.chunk_pipeline, documents=[doc])
    return {
        "meeting_id": body.meeting_id,
        "chunks": [
            {"chunk_index": i, "text": node.text}
            for i, node in enumerate(nodes)
        ],
    }
