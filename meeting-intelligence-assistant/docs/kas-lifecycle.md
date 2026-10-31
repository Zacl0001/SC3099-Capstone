# KAS ingestion and deletion

The backend calls KAS over HTTP; KAS owns the vector store. The active entry
point is `module4-knowledge assistant service/app.py` (`uvicorn app:app`).

## Deleting a meeting

`DELETE /api/meetings/{id}` in the backend:

1. Checks that the current user owns the meeting.
2. Calls KAS `DELETE /meetings/meeting-{id}`.
3. Deletes the transcript and meeting rows and commits.
4. Removes the uploaded transcript file.

KAS deletes by source document ID directly in the vector store. It handles
both HTTP ingestion IDs (`meeting-7`) and standalone ingestion IDs
(`meeting:meeting-7`). For canonical backend IDs such as `meeting-7`, it also
removes older numeric source IDs (`7` and `meeting:7`). Missing chunks are successful deletions, so retries
are safe. No embedding or LLM call is needed.

If KAS is unavailable or deletion fails, the backend returns HTTP 503 and
keeps the meeting, transcript row, and file. Retry the same backend request
after KAS recovers. If chunk cleanup succeeds but the backend database commit
fails, retry deletion, or use `POST /api/meetings/{id}/index` to restore chunks
for the retained meeting. This is not a transaction across both services.

Restart both backend and KAS after deploying this change. Meetings deleted
before this change still require a separate orphan cleanup; this endpoint
does not automatically discover them. KAS is an internal service: ownership
checks are performed by the backend, so do not expose KAS directly to users.

## Which KAS files are active?

| File | Role |
| --- | --- |
| `app.py` | Active HTTP service; ingestion, retrieval, chunking, deletion |
| `ingestion.py` | Active document conversion and chunk transforms; also contains standalone `MeetingIngestor` and JSON helpers |
| `embedding.py` | Active embedding model factory |
| `vector_store.py` | Active vector store factory |
| `config.py` | Active configuration |
| `service.py` | Standalone `KnowledgeAssistant` wrapper; not imported by the HTTP service |
| `retriever.py` | Standalone retriever used by `service.py`; not imported by the HTTP service |
| `test_kas.py` | Manual demo that ingests sample JSON and searches; not an automated regression test |
| `data/sample_meeting1.json`, `data/sample_meeting2.json` | Inputs for the manual demo |
| `view_chunks.py` | Optional read-only command-line inspection utility |
| `EY KAS description` | Reference text, not executable service code |
| `__init__.py` | Package marker for package-style imports |
| `requirements.txt`, `pyproject.toml` | Dependency and project metadata |
| `tests/test_deletion.py` | Automated deletion regression tests |

Keep `ingestion.py`: although the HTTP app does not use its `MeetingIngestor`
class, it imports other functions and transformations from the same file.
The standalone files are still connected to the manual demo, so they have
not been deleted.

## Regression checks

From `module2-backend`, with backend development dependencies installed:

```sh
DATABASE_URL=sqlite:// python -m pytest tests/test_meeting_deletion.py tests/test_ai_proxy.py tests/test_transcripts.py -q
```

From `module4-knowledge assistant service`, with KAS dependencies and pytest installed:

```sh
python -m pytest tests/test_deletion.py -q
```

These tests use mocked backend sessions and an actual in-memory vector store.
They do not connect to a running PostgreSQL database or Ollama.
