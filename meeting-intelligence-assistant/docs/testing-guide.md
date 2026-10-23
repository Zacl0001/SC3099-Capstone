# Testing and local setup guide

This guide covers setting up all four services, running each module's tests, and
running the application-wide suite on Windows / PowerShell.

## Components and ports

| Component | Folder | Port | Started with |
| --- | --- | --- | --- |
| Frontend | `module1-frontend` | 3000 | `npm run dev` |
| Backend API | `module2-backend` | 8000 | `uvicorn app.main:app` |
| AI processing service | `module3-AI processing service` | 8001 | `uvicorn app.main:app` |
| Knowledge assistant (KAS) | `module4-knowledge assistant service` | 8002 | `uvicorn app:app` |
| PostgreSQL (pgvector) | Docker container `meeting-db` | 5432 | `docker start meeting-db` |
| Ollama | host service | 11434 | Ollama app |

Required models: `qwen2.5:7b-instruct` and `nomic-embed-text`
(`ollama pull <model>`).

## One-time setup

Run from the `SC3099-Capstone` repository root unless noted otherwise.

### 1. PostgreSQL (pgvector)

```powershell
docker run --name meeting-db -e POSTGRES_USER=meeting_app -e POSTGRES_PASSWORD=meeting_local_dev -e POSTGRES_DB=meeting_intelligence -p 127.0.0.1:5432:5432 -v meeting_pgdata:/var/lib/postgresql/data -d pgvector/pgvector:pg17
docker exec meeting-db psql -U meeting_app -d meeting_intelligence -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

On later sessions just run `docker start meeting-db`.

### 2. Backend (module2)

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\meeting-intelligence-assistant\module2-backend\requirements-dev.txt
Copy-Item .\meeting-intelligence-assistant\.env.example .\meeting-intelligence-assistant\module2-backend\.env
```

Edit `module2-backend\.env` so the credential matches the container:

```dotenv
DATABASE_URL=postgresql+psycopg://meeting_app:meeting_local_dev@127.0.0.1:5432/meeting_intelligence
```

Apply migrations from `module2-backend`:

```powershell
..\..\.venv\Scripts\python.exe -m alembic upgrade head
```

`requirements-dev.txt` adds `pytest` on top of the backend runtime requirements.

### 3. AI service (module3)

```powershell
cd ".\meeting-intelligence-assistant\module3-AI processing service"
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Defaults already point at Ollama (`http://localhost:11434/v1`) and KAS
(`http://localhost:8002`). A `.env` is optional; see `.env.example`.

### 4. Knowledge service (module4)

```powershell
cd ".\meeting-intelligence-assistant\module4-knowledge assistant service"
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Connection settings live in `config.py` and must match the `meeting-db`
credentials.

### 5. Frontend (module1)

```powershell
cd ".\meeting-intelligence-assistant\module1-frontend"
npm install
Copy-Item .env.example .env.local
```

`.env.local` defaults are correct for local development. AI features stay
mock (`NEXT_PUBLIC_MOCK_AI=true`) until the backend AI routes are wired.

## Start and stop everything

```powershell
cd .\meeting-intelligence-assistant
.\scripts\start-all.ps1
# ... work ...
.\scripts\stop-all.ps1
```

`start-all.ps1` starts Postgres, waits for it, then launches KAS, module3,
module2 and the frontend in separate windows, waiting for each port.
`stop-all.ps1` stops the listeners on 3000/8000/8001/8002 and the database
container (`-KeepDb` leaves Postgres running).

Manual start order (always DB first):

```powershell
docker start meeting-db
# terminal A, module4 folder
.\.venv\Scripts\python.exe -m uvicorn app:app --port 8002
# terminal B, module3 folder
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8001
# terminal C, module2 folder
..\..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
# terminal D, module1 folder
npm run dev
```

## Testing

### Static checks (no services)

```powershell
cd .\meeting-intelligence-assistant\module1-frontend
npm run lint
npm run typecheck
```

### Offline unit tests (no services)

Backend (2 tests; auth/meetings/chat suites are still placeholders):

```powershell
cd .\meeting-intelligence-assistant\module2-backend
..\..\.venv\Scripts\python.exe -m pytest tests -q
```

AI service (59 tests):

```powershell
cd .\meeting-intelligence-assistant\module3-AI processing service
.\.venv\Scripts\python.exe -m pytest -q --ignore=tests/test_integration_live.py
```

Do not run `pytest` from the repository root: it collects the legacy
`OLD tests/` template suite, which needs a different stack.

### KAS acceptance (Postgres + KAS + Ollama running)

Covered automatically by `test-all.ps1 -Live`. Manual equivalent:

```powershell
$kas = 'http://127.0.0.1:8002'
Invoke-RestMethod "$kas/health" -Method Post
$body = Get-Content '.\meeting-intelligence-assistant\module4-knowledge assistant service\data\sample_meeting1.json' -Raw
Invoke-RestMethod "$kas/ingest" -Method Post -ContentType 'application/json' -Body $body
Invoke-RestMethod "$kas/ingest" -Method Post -ContentType 'application/json' -Body $body   # same chunk count = idempotent
Invoke-RestMethod "$kas/search" -Method Post -ContentType 'application/json' -Body '{"meeting_id":"meeting-001-kas-failure-debug","query":"database connection error","top_k":3}'
Invoke-RestMethod "$kas/chunk" -Method Post -ContentType 'application/json' -Body '{"transcript":"Alice: We discussed the budget. Bob: We approved it."}'
```

Swagger shortcuts: <http://localhost:8002/docs>.

### Live AI integration (Postgres + KAS + Ollama running)

Run from the module3 folder through the conductor (checks prerequisites first):

```powershell
.\.venv\Scripts\python.exe run_tests.py --tier smoke   # real LLM + real /chunk, ~2-4 min
.\.venv\Scripts\python.exe run_tests.py --tier live    # integration, ~5-10 min
.\.venv\Scripts\python.exe run_tests.py --tier all     # offline -> smoke -> live
.\.venv\Scripts\python.exe run_tests.py --tier live --full-live   # production 20k threshold, 45+ min
```

The live tier lowers `CHUNK_THRESHOLD_CHARS` to 4000 so the long-transcript
test finishes in minutes. `--full-live` uses the real 20000 default.

Run the live pytest file directly (never uses the reduced threshold unless you
export it):

```powershell
$env:INTEGRATION='1'; $env:CHUNK_THRESHOLD_CHARS='4000'
.\.venv\Scripts\python.exe -m pytest tests/test_integration_live.py -v
```

### Application-level workflow (manual)

Backend API (services running) - Swagger at <http://localhost:8000/docs>:

1. `POST /api/auth/register` with a new email and 8+ char password (201).
2. `POST /api/auth/login`, then use **Authorize** with the access token.
3. `GET /api/auth/me`.
4. `POST /api/meetings/upload` with a UTF-8 `.txt` file whose lines are
   `Speaker: text`.
5. `GET /api/meetings`.
6. `POST /api/meetings/{meeting_id}/transcript/process`.
7. `GET /api/meetings/{meeting_id}/transcript`.

Frontend (`http://localhost:3000`): register/login, create a meeting from a
transcript, open it, and verify summary/actions/decisions/chat. These AI views
come from the browser-side mock until `module2` forwards to module3/module4.

KAS/AI Swagger UIs: <http://localhost:8002/docs>, <http://localhost:8001/docs>.

## Application-wide runner

```powershell
cd .\meeting-intelligence-assistant
.\scripts\test-all.ps1              # T0 + T1 + module4 import check
.\scripts\test-all.ps1 -Live        # adds KAS acceptance + module3 smoke + live
.\scripts\test-all.ps1 -Live -FullLive   # live tier at the real 20k threshold
```

The runner prints a PASS/FAIL table and exits nonzero if any step fails.
It does not start services; use `start-all.ps1` first for `-Live`.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `fatal: bad object HEAD` | Local git objects are incomplete (see note below). Tests do not need git. |
| Docker pipe not found | Start Docker Desktop, wait for the engine, then retry. |
| `No module named app` | Run uvicorn/pytest from the module folder, not the repo root. |
| `No module named pytest` | Use the venv python that has the test deps installed (`requirements-dev.txt` for module2). |
| `INTEGRATION` skips | Live tests are skipped unless `INTEGRATION=1`; the conductor sets it. |
| Live tier says :5433 | You are on an old copy of `run_tests.py`; it now checks :5432. |
| `docker compose up -d` mentioned | Stale instruction; this project uses the `meeting-db` container. |
| KAS 503 | Ollama is not running or the embedding model is missing. |
| Backend DB auth failure | `module2-backend/.env` must match the password used when the volume was created. |
| Port already in use | Stop the old process (`stop-all.ps1`) or reuse the running service. |


