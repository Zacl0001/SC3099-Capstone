# Backend local setup (Windows / PowerShell)

This guide runs FastAPI on your computer and PostgreSQL in Docker. Each teammate has a separate local database and uploaded files; Git shares code and migrations, not records or files.

The current backend supports authentication, meeting uploads/listing, and parsing and saving transcripts. AI summarization and KAS indexing are separate service integrations.

## 1. Prerequisites

- Git and a clone of this repository.
- Python 3.12 (including the Windows `py` launcher).
- [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/), installed and running with Linux containers. Follow its WSL 2 setup instructions if prompted.

Open PowerShell in your cloned `SC3099-Capstone` repository root. Use your own clone location, not another teammate's absolute path.

```powershell
py -3.12 --version
docker info
```

The first command checks Python. The second checks that Docker's engine is running.

Do not use `ToUpdate docker-compose.yml` for this setup: it still contains the old project template configuration.

## 2. Create PostgreSQL once

For a fresh setup, run:

```powershell
docker run --name meeting-db -e POSTGRES_USER=meeting_app -e POSTGRES_PASSWORD=meeting_local_dev -e POSTGRES_DB=meeting_intelligence -p 127.0.0.1:5432:5432 -v meeting_pgdata:/var/lib/postgresql/data -d pgvector/pgvector:pg17
```

- `--name` names the container `meeting-db`.
- The three `-e` options set the username, local-development password and database name.
- `-p` exposes PostgreSQL on port 5432 on this computer only.
- `-v` stores database data in the persistent Docker volume `meeting_pgdata`.
- `-d` runs the container in the background.
- The image provides PostgreSQL 17 with the pgvector extension available. Installing the extension into the database is a separate KAS setup step if needed.

`meeting_local_dev` is an example local-only password. If you choose another password, use the matching value in `.env` below.

Check startup:

```powershell
docker exec meeting-db pg_isready -U meeting_app -d meeting_intelligence
```

Wait until this reports that PostgreSQL is accepting connections.

If `meeting-db` already exists, use `docker start meeting-db` instead of creating it again. Keep its existing credentials. Changing the environment variables does not reset credentials in an existing database volume.

## 3. Install Python dependencies

From the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\meeting-intelligence-assistant\module2-backend\requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

1. Creates a local virtual environment. Skip this line if you already have the project's environment.
2. Installs the backend's pinned dependencies into that environment.
3. Checks for dependency conflicts.

These commands use the environment's Python directly, so activation is not required. Do not run `-m` by itself; it is an option passed to Python.

## 4. Configure the backend

Copy `meeting-intelligence-assistant/.env.example` to `meeting-intelligence-assistant/module2-backend/.env` if you do not already have that file. Do not overwrite an existing local `.env`.

In the backend `.env`, set:

```dotenv
DATABASE_URL=postgresql+psycopg://meeting_app:meeting_local_dev@127.0.0.1:5432/meeting_intelligence
```

This selects the psycopg driver, username, password, local host/port and database. Match the credentials to step 2. Special characters in a custom password need URL encoding.

The backend explicitly loads `.env` from `module2-backend`; placing it only at the repository or project root will not work. Keep `.env` and `.venv` out of Git. `migrations/env.py` is Python migration configuration, not the credentials file.

## 5. Create/update tables

From the repository root:

```powershell
cd .\meeting-intelligence-assistant\module2-backend
..\..\.venv\Scripts\python.exe -m alembic upgrade head
..\..\.venv\Scripts\python.exe -m alembic current
```

1. Enters the backend directory containing `alembic.ini`.
2. Applies the repository's existing migrations.
3. Displays the database's applied revision.

For initial setup, do not generate new migrations with `revision --autogenerate`. That command is for intentional model/schema changes.

## 6. Start the API

Stay in `meeting-intelligence-assistant/module2-backend`:

```powershell
..\..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

This loads the FastAPI `app` object from `app/main.py`. `--reload` restarts the development server when source files change. Keep this terminal open.

Open [Swagger API documentation](http://127.0.0.1:8000/docs). Wait for `Application startup complete` in the terminal.

The `/` URL returning 404 is normal: there is no homepage route.

## 7. Verify the workflow in Swagger

1. Execute `POST /api/auth/register` with a new test email and a password of at least eight characters. Expect 201.
2. Execute `POST /api/auth/login` with the same credentials. Expect 200 and an `access_token`.
3. Click **Authorize**, paste only the token (without quotes or the word `Bearer`), and confirm. Login alone does not update Swagger's authorization.
4. Execute `GET /api/auth/me`. Expect your test user's details.
5. Save this content as a UTF-8 file named `test.txt`:

   ```text
   Alex: Let us review our project.
   Jamie: I will test the upload endpoint.
   Alex: We will review the results tomorrow.
   ```

   Each nonempty line must contain `Speaker: text`.

6. Execute `POST /api/meetings/upload`, entering a title and selecting the file. Expect 201; note the returned meeting ID.
7. Execute `GET /api/meetings`. Expect the new meeting in your account's list.
8. Execute `POST /api/meetings/{meeting_id}/transcript/process` using that ID. Expect 200 with parsed sections saved to the database.
9. Execute `GET /api/meetings/{meeting_id}/transcript`. Expect the saved sections.

POST processing reads the file, parses speaker turns and saves the result. GET retrieves that saved result. This processing endpoint does not generate AI summaries or embeddings.

Swagger's lower **Responses** section documents possible outcomes, including 422. Check **Server response** for the actual result of your request.

## Storage and supported formats

- PostgreSQL stores users, sessions, meetings, transcript metadata and parsed sections.
- Uploaded originals are stored under `meeting-intelligence-assistant/storage/transcripts/`, created automatically.
- Supported extensions: `.txt`, `.pdf`, `.docx`; maximum file size: 10 MiB.
- TXT must be UTF-8. PDF must contain extractable text and must not be encrypted; there is no OCR for scanned PDFs.
- DOCX extraction reads normal paragraphs, not tables or text boxes.
- The parser expects `Speaker: text` on each nonempty extracted line. Headers and wrapped PDF lines can require cleanup.

Local files and database rows are separate. Keeping the Docker volume does not back up uploaded files.

## Subsequent sessions

Open Docker Desktop. From a new PowerShell terminal at the repository root:

```powershell
docker start meeting-db
cd .\meeting-intelligence-assistant\module2-backend
..\..\.venv\Scripts\python.exe -m alembic upgrade head
..\..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

These start the existing database, enter the backend directory, apply any new migrations and start the API. After pulling dependency changes, reinstall `requirements.txt` using the environment's Python.

To stop, press Ctrl+C in the Uvicorn terminal, then run `docker stop meeting-db`. Neither action deletes stored data.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Docker daemon connection error | Open Docker Desktop and wait for the engine to start. |
| Container name already in use | Use `docker start meeting-db`; do not recreate an existing database. |
| Port 5432 already allocated | Another PostgreSQL/container may be running. Use the intended existing database, or choose a free host port and update `.env` to match. |
| `No module named app` | Run Uvicorn from `module2-backend`. |
| `No module named alembic` or another installed package | Use the repository `.venv` Python, not the global interpreter. |
| `No script_location key found` | Run Alembic from `module2-backend`, where `alembic.ini` lives. |
| Missing `DATABASE_URL` | Check that `module2-backend/.env` exists and contains the setting. |
| Database connection timeout | Check Docker/container readiness and the host/port in `.env`. |
| Database password authentication failed | Match `.env` to the credentials used when the database volume was first initialized. |
| 401 Invalid or expired session | Log in again and replace the old Swagger authorization token. |
| GET transcript returns 409 | Process that transcript first with the POST endpoint. |
| Processing returns 422 | Read the response detail; check the extracted text's `Speaker: text` format. |

## Team integration

`localhost` always refers to the computer running the client. These instructions give everyone an independent environment; they do not share accounts, records or files.

Frontend developers should use `http://127.0.0.1:8000` as the local API base URL. Browser calls from another origin need CORS configured in the backend; Swagger working does not prove cross-origin frontend calls are enabled.

AI/KAS services running inside Docker cannot use `localhost` to reach FastAPI on the host. On Docker Desktop, host access commonly uses `host.docker.internal`, and the API must listen on a reachable interface. Agree on service networking separately from this loopback-only setup.
