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

Full setup and testing instructions are in the [testing guide](docs/testing-guide.md). Short version (Windows / PowerShell):

1. Start Docker Desktop, then `docker start meeting-db`.
2. Start Ollama with `qwen2.5:7b-instruct` and `nomic-embed-text`.
3. Knowledge service: `module4-knowledge assistant service` -> `.\.venv\Scripts\python.exe -m uvicorn app:app --port 8002`
4. AI service: `module3-AI processing service` -> `.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8001`
5. Backend: follow the [backend setup guide](module2-backend/README.md) (root `.venv`, `.env`, `alembic upgrade head`, then `uvicorn app.main:app --port 8000`).
6. Frontend: `module1-frontend` -> `npm install`, `npm run dev`.

Or start everything at once:

```powershell
.\scripts\start-all.ps1
.\scripts\stop-all.ps1
```

The existing `ToUpdate docker-compose.yml` contains the old template configuration and is not the current setup procedure.

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
