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

cp .env.example .env

docker compose up --build

## Services

Frontend: http://localhost:3000
Backend: http://localhost:8000
AI Service: http://localhost:8001
Knowledge Service: http://localhost:8002
