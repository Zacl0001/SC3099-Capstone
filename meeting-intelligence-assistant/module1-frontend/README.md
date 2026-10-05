# Module 1 – Frontend (User Portal)

Next.js 16 (App Router) + TypeScript + Tailwind CSS 4.

## Features

| Page | What it does |
| --- | --- |
| `/` | Landing page |
| `/register`, `/login` | Account creation and sign-in (`/api/auth/*`) |
| `/dashboard` | Welcome, stats, upload a transcript, recent meetings |
| `/meetings` | All meetings in the account – search, filter by status, sort |
| `/meetings/new` | Upload a transcript (file drag-and-drop or paste text, with a sample transcript) |
| `/meetings/[id]` | Processing status (auto-refreshes), then tabs for **Summary**, **Action items**, **Decisions**, **Ask AI** (chat with clickable citations) and **Transcript** (searchable; citations and "View in transcript" links scroll to and highlight the source line) |

`/dashboard` and `/meetings/*` redirect to `/login` when signed out, then send you back to the page you asked for after sign-in.

## Running locally

```bash
cd module1-frontend
npm install
cp .env.example .env.local   # optional – see below
npm run dev                  # http://localhost:3000
```

Other scripts: `npm run build`, `npm start`, `npm run lint`, `npm run typecheck`.

### Configuration (`.env.local`)

| Variable | Default | Meaning |
| --- | --- | --- |
| `BACKEND_URL` | `http://localhost:8000` | Where `/api/*` is proxied (module2). Read at **build** time. |
| `NEXT_PUBLIC_MOCK_AUTH` | `true` | Fake login/register in the browser |
| `NEXT_PUBLIC_MOCK_MEETINGS` | `true` | Fake meetings, transcripts, AI outputs and chat in the browser |

With no `.env.local` everything is mocked, so the UI works with no backend running. Mock data lives in the browser's `localStorage`, and the mock "AI" is keyword matching. A **Demo mode** badge shows in the navbar while any mock is on.

The backend auth endpoints already exist, so `NEXT_PUBLIC_MOCK_AUTH=false` + `NEXT_PUBLIC_MOCK_MEETINGS=true` uses real accounts with mocked meeting features. (Mock auth + real meetings isn't supported, because the backend would reject the fake token.) Restart `npm run dev` after changing these.

### How it talks to the backend

The browser only calls relative `/api/...` URLs. `next.config.js` rewrites them to `BACKEND_URL`, so the backend needs no CORS setup. All calls are in `lib/api.ts`, and the response types are in `lib/types.ts` (snake_case, matching Pydantic).

Auth uses the bearer token from `POST /api/auth/login`, stored in `localStorage` and sent as `Authorization: Bearer <token>`. Any 401 logs the user out.

## API contract expected from module2

Auth endpoints are implemented in the backend. The rest is what the frontend expects:

| Method | Path | Body | Response |
| --- | --- | --- | --- |
| POST | `/api/auth/register` | `{email, password}` | `User {id, email}` (409 if taken) |
| POST | `/api/auth/login` | `{email, password}` | `{access_token, token_type, expires_at}` |
| GET | `/api/auth/me` | – | `User` |
| POST | `/api/auth/logout` | – | 204 |
| GET | `/api/meetings` | – | `Meeting[]` (current user's only) |
| POST | `/api/meetings` | `{title, description?}` | `Meeting` (status `uploaded`) |
| GET | `/api/meetings/{id}` | – | `Meeting` |
| DELETE | `/api/meetings/{id}` | – | 204 |
| POST | `/api/meetings/{id}/transcript` | multipart, field `file` | `Transcript` |
| GET | `/api/meetings/{id}/transcript` | – | `Transcript {meeting_id, file_name, raw_text, created_at}` |
| POST | `/api/meetings/{id}/process` | – | `Meeting` (status `processing`) |
| GET | `/api/meetings/{id}/summary` | – | `{summary, key_points[], topics?[]}` |
| GET | `/api/meetings/{id}/action-items` | – | `[{id, task, assignee?, deadline?, status?, evidence?, timestamp?}]` |
| GET | `/api/meetings/{id}/decisions` | – | `[{id, decision, evidence?, timestamp?}]` |
| POST | `/api/meetings/{id}/chat` | `{question}` | `{answer, citations: [{chunk_id, start_time?, end_time?, speaker?, text}]}` |

`Meeting` = `{id, title, description?, status: "uploaded" | "processing" | "completed" | "failed", created_at, updated_at?, transcript_file_name?, error_message?}`.

Notes for the backend and AI teams:

- The meeting page polls `GET /api/meetings/{id}` every 3 s while `status == "processing"`. The summary, action item and decision endpoints are only called once the status is `completed`.
- Errors should use FastAPI's `{"detail": "..."}` shape, which the UI shows to the user.
- Accepted upload types are `.txt .md .vtt .srt`, up to 5 MB (`lib/config.ts`).
- **Citations:** the answer text can include `[1]`, `[2]`… markers that refer to positions in `citations` and render as clickable chips. The UI finds the matching transcript line by `start_time` (e.g. `00:01:23`) or by the citation's `text` appearing in the transcript, so return verbatim transcript text where possible. `evidence`/`timestamp` on action items and decisions are matched the same way.

## Structure

```
app/                    routes (see table above)
components/
  auth/                 AuthProvider (context), ProtectedRoute, LoginForm, RegisterForm
  common/               AppShell, Navbar, Button, Modal, LoadingSpinner, ErrorMessage, Icons…
  meetings/             UploadTranscript, MeetingList/Card, MeetingStatus, TranscriptViewer
  summary/              SummaryView
  action-items/         ActionItemList, ActionItemCard
  decisions/            DecisionList
  chat/                 ChatWindow, ChatMessage, ChatInput, Citation, CitationList
lib/
  api.ts                every backend call (switches to mock.ts when mocks are on)
  mock.ts               in-browser mock backend
  types.ts              data contract
  auth.ts               token storage
  transcript.ts         transcript parser + citation → line matching
```

## Docker

```bash
docker build --build-arg BACKEND_URL=http://backend:8000 -t mia-frontend .
docker run -p 3000:3000 mia-frontend
```

Mocks are **off** by default in the Docker build. To turn them on, pass `--build-arg NEXT_PUBLIC_MOCK_MEETINGS=true`.
