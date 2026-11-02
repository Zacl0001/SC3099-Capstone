[//]: # (Purpose: Main documentation and entry point for the entire project.)

[//]: # ()
[//]: # (Implement:)

[//]: # ()
[//]: # (1. Project overview)

[//]: # (2. Problem statement)

[//]: # (3. Features)

[//]: # (4. Architecture diagram)

[//]: # (5. Technology stack)

[//]: # (6. Repository structure)

[//]: # (7. How to run locally)

[//]: # (8. Environment variables)

[//]: # (9. API documentation)

[//]: # (10. Testing)

[//]: # (11. Deployment)

[//]: # (12. Team members)

[//]: # (Owner: Everyone, with Student 4 coordinating.)


# Meeting Intelligence Assistant

AI-powered meeting analysis and knowledge assistant developed for NTU.

## Architecture

Frontend
    ↓
Backend API
    ↓
├── AI Processing Service
└── Knowledge Assistant Service

## Features

- User authentication
- Meeting transcript upload
- Meeting summarization
- Action item extraction
- Decision extraction
- Topic identification
- Semantic transcript search
- RAG-based Q&A
- Source citations

## Tech Stack

Frontend:
- Next.js
- TypeScript
- Tailwind CSS

Backend:
- FastAPI
- PostgreSQL

AI:
- Python
- LLM API

Knowledge:
- Embeddings
- pgvector
- RAG

Infrastructure:
- Docker
- Object storage

## Running locally
## Prerequisites

- Python 3.12
- Node.js LTS
- Docker Desktop
- Docker Compose

## Installation

1. Clone the repository.
2. Run `.\scripts\setup.ps1` from \meeting-intelligence-assistant
3. Configure your `.env` files.

## Start
Run `.\scripts\start-all.ps1`.

or start manually:
1. Start Docker Desktop, then `docker start meeting-db`.
2. Start Ollama with `qwen2.5:7b-instruct` and `nomic-embed-text`.
3. Knowledge service: `module4-knowledge assistant service` -> `.\.venv\Scripts\python.exe -m uvicorn app:app --port 8002`
4. AI service: `module3-AI processing service` -> `.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8001`
5. Backend: follow the [backend setup guide](module2-backend/README.md) (root `.venv`, `.env`, `alembic upgrade head`, then `uvicorn app.main:app --port 8000`).
6. Frontend: `module1-frontend` -> `npm install`, `npm run dev`.

Full setup and testing instructions are in the [testing guide](docs/testing-guide.md). Short version (Windows / PowerShell):

## Services

Frontend: http://localhost:3000
Backend: http://localhost:8000
AI Service: http://localhost:8001
Knowledge Service: http://localhost:8002

## Testing

Run the application-wide suite from this folder:

```powershell
.\scripts\test-all.ps1          # static + offline tests
.\scripts\test-all.ps1 -Live    # adds KAS acceptance + live AI integration
```

Per-module commands, tiers and troubleshooting are documented in the [testing guide](docs/testing-guide.md).

## Evaluation

With the stack running, score the AI pipeline against the hand-written expected
results in `evaluation/` (run from this folder):

```powershell
..\.venv\Scripts\python.exe evaluation\evaluate.py --threshold 0.6
```

It reports summary correctness, action-item/decision precision, recall and F1,
plus RAG retrieval, citation and grounding scores. Add `--delete` to remove the
evaluation meetings afterwards. See
[AI quality evaluation](docs/testing-guide.md#ai-quality-evaluation-all-services-running)
for the expected-file format and how matching works.

## Stop
Run `.\scripts\stop-all.ps1`.

