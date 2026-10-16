# Module 1 – Frontend (User Portal)

Next.js 16 (App Router) + TypeScript + Tailwind CSS 4.

## Features

| Page | What it does |
| --- | --- |
| `/` | Landing page |
| `/register`, `/login` | Account creation and sign-in (`/api/auth/*`) |
| `/dashboard` | Welcome, stats, upload a transcript, recent meetings |
| `/meetings` | All meetings in the account – search, sort (and filter by status when the backend provides one) |
| `/meetings/new` | Upload a transcript (`.txt`/`.pdf`/`.docx` drag-and-drop, or paste text, with a sample transcript) |
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
| `NEXT_PUBLIC_MOCK_AUTH` | `false` | Fake accounts in the browser. Turns the two below on as well. |
| `NEXT_PUBLIC_MOCK_MEETINGS` | `false` | Fake meetings and transcripts in the browser. Turns `MOCK_AI` on as well. |
| `NEXT_PUBLIC_MOCK_AI` | `true` | Compute summary, action items, decisions and chat in the browser from the transcript |

The defaults follow what module2 currently implements:

| Feature | module2 | Frontend uses |
| --- | --- | --- |
| Register, login, current user, logout | Implemented | **Real backend** |
| Upload meeting, list meetings | Implemented | **Real backend** |
| Process transcript into speaker sections, get transcript | Implemented | **Real backend** |
| Get one meeting | Not yet | Looked up from the meeting list. Status comes from the transcript endpoint: 409 means not processed yet. |
| Delete meeting | Not yet | Delete button hidden |
| Summary, action items, decisions, chat | Not yet | Computed in the browser from the **real** transcript using keyword matching, not an LLM |

You need module2 running on `BACKEND_URL` with its database migrated (`alembic upgrade head`). A **Demo mode** badge shows in the navbar while the AI features are simulated. Once module2 serves the AI endpoints in the contract below, set `NEXT_PUBLIC_MOCK_AI=false`.

To run the UI with no backend at all, set `NEXT_PUBLIC_MOCK_AUTH=true`. Restart `npm run dev` after changing any of these.

**Transcript format.** module2 requires every non-empty line to be `Speaker: text`. Any other line makes processing fail with a 422 error, which the meeting page shows along with a retry button. The built-in sample transcript uses this format.

### How it talks to the backend

The browser only calls relative `/api/...` URLs. `next.config.js` rewrites them to `BACKEND_URL`, so the backend needs no CORS setup. All calls are in `lib/api.ts`, and the response types are in `lib/types.ts` (snake_case, matching Pydantic).

Auth uses the bearer token from `POST /api/auth/login`, stored in `localStorage` and sent as `Authorization: Bearer <token>`. On page load the session is checked with `GET /api/auth/me`. A 401 at any point logs the user out. If the backend can't be reached, signed-in pages show a "Can't reach the server" panel with a retry button instead of logging the user out.

## API contract

### Implemented in module2 (used as-is)

| Method | Path | Body | Response |
| --- | --- | --- | --- |
| POST | `/api/auth/register` | `{email, password}` | `{id, email}` (409 if taken) |
| POST | `/api/auth/login` | `{email, password}` | `{access_token, token_type, expires_at}` |
| GET | `/api/auth/me` | – | `{id, email}` |
| POST | `/api/auth/logout` | – | 204 |
| GET | `/api/meetings` | – | `[{id, title, created_at}]` (current user's only) |
| POST | `/api/meetings/upload` | multipart: `title`, `file` (`.txt`/`.pdf`/`.docx`, ≤ 10 MB) | `{id, title, created_at}` |
| POST | `/api/meetings/{id}/transcript/process` | – | `{meeting_id, title, sections: [{section_id, speaker_id, speaker_name, text}]}` (422 on bad format) |
| GET | `/api/meetings/{id}/transcript` | – | same as above (409 until processed) |

### Still needed from module2 (the frontend is ready for these)

| Method | Path | Response | Notes |
| --- | --- | --- | --- |
| GET | `/api/meetings/{id}` | `Meeting` | Lets the page skip the list lookup |
| DELETE | `/api/meetings/{id}` | 204 | Then set `CAN_DELETE_MEETINGS` in `lib/config.ts` |
| GET | `/api/meetings/{id}/summary` | `{summary, key_points[], topics?[]}` | |
| GET | `/api/meetings/{id}/action-items` | `[{id?, task, assignee?, deadline?, status?, evidence?, timestamp?}]` | module3's `{action_items: [...]}` wrapper is also accepted. Missing ids are generated. |
| GET | `/api/meetings/{id}/decisions` | `[{id?, decision, evidence?, timestamp?}]` | module3's `{decisions: [...]}` wrapper is also accepted |
| POST | `/api/meetings/{id}/chat` | `{answer, citations: [{chunk_id, start_time?, end_time?, speaker?, text}]}` | Body `{question}` |

An optional `status: "uploaded" | "processing" | "completed" | "failed"` on meetings would also let the list show status badges. If the AI step becomes asynchronous, the meeting page polls `GET /api/meetings/{id}` every 3 s while the status is `processing`.

Notes for the backend and AI teams:

- Errors should use FastAPI's `{"detail": "..."}` shape, which the UI shows to the user.
- **Citations:** the answer text can include `[1]`, `[2]`… markers that refer to positions in `citations` and render as clickable chips. The UI finds the matching transcript line in this order:
  1. `chunk_id` equal to a transcript `section_id` (best)
  2. `start_time`
  3. the citation's `text` appearing verbatim in the transcript

  `evidence`/`timestamp` on action items and decisions are matched the same way.

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
  mock.ts               in-browser mock backend + keyword "AI" (also used on real transcripts)
  types.ts              data contract
  auth.ts               token storage
  transcript.ts         transcript parser, module2 sections → display lines, citation matching
```

## Docker

```bash
docker build --build-arg BACKEND_URL=http://backend:8000 -t mia-frontend .
docker run -p 3000:3000 mia-frontend
```

The Docker build uses the same defaults: real auth and meetings, with the AI features computed in the browser. Override them with `--build-arg NEXT_PUBLIC_MOCK_AI=false` and similar.
