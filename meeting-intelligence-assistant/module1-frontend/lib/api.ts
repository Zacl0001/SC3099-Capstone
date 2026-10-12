// Centralised API communication.
//
// Every backend call goes through this file. Requests use relative /api/*
// URLs which next.config.js proxies to module2-backend.
//
// Feature flags in config.ts route calls to lib/mock.ts for anything module2
// does not implement yet.
//
// module2 endpoints used:
//   POST   /api/auth/register                    {email, password}      -> User
//   POST   /api/auth/login                       {email, password}      -> TokenResponse
//   GET    /api/auth/me                                                 -> User
//   POST   /api/auth/logout                                             -> 204
//   GET    /api/meetings                                                -> {id, title, created_at}[]
//   POST   /api/meetings/upload                  multipart title + file -> {id, title, created_at}
//   POST   /api/meetings/{id}/transcript/process                        -> Transcript (sections)
//   GET    /api/meetings/{id}/transcript                                -> Transcript (409 until processed)
//
// Not in module2 yet (mocked / worked around until they exist):
//   GET    /api/meetings/{id}                  -> looked up from GET /api/meetings
//   DELETE /api/meetings/{id}                  -> Delete button hidden
//   GET    /api/meetings/{id}/summary          -> Summary         } computed in the browser from
//   GET    /api/meetings/{id}/action-items     -> ActionItem[]    } the real transcript while
//   GET    /api/meetings/{id}/decisions        -> Decision[]      } NEXT_PUBLIC_MOCK_AI=true
//   POST   /api/meetings/{id}/chat  {question} -> ChatResponse    }

import { clearToken, getToken, saveToken } from './auth';
import { MOCK_AI, MOCK_AUTH, MOCK_MEETINGS } from './config';
import { ApiError } from './errors';
import * as mock from './mock';
import { segmentsOf } from './transcript';
import type {
  ActionItem,
  ChatResponse,
  Decision,
  Meeting,
  MeetingStatus,
  Summary,
  Transcript,
  User,
} from './types';

export { ApiError };

export const UNAUTHORIZED_EVENT = 'mia:unauthorized';

type Id = number | string;

// FastAPI errors look like {"detail": "msg"} or {"detail": [{"msg": "..."}]}.
function extractDetail(body: unknown, fallback: string): string {
  if (body && typeof body === 'object' && 'detail' in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((d) => (d && typeof d === 'object' && 'msg' in d ? String(d.msg).replace(/^Value error, /, '') : ''))
        .filter(Boolean)
        .join('; ') || fallback;
    }
  }
  return fallback;
}

function handleUnauthorized(path: string) {
  // A failed login is a normal 401 and must not trigger a global logout.
  if (path.startsWith('/api/auth/login')) return;
  clearToken();
  cachedUser = null;
  clearCaches();
  window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json');

  let res: Response;
  try {
    res = await fetch(path, { ...init, headers });
  } catch {
    throw new ApiError('Cannot reach the server. Please check your connection.', 0);
  }

  if (res.status === 204) return undefined as T;

  const text = await res.text();
  let body: unknown = undefined;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = text;
    }
  }

  if (!res.ok) {
    if (res.status === 401) handleUnauthorized(path);
    // A non-JSON 5xx comes from the Next.js proxy (backend down) or an unhandled backend error.
    const fallback =
      res.status >= 500
        ? typeof body === 'object'
          ? 'The server ran into a problem. Please try again.'
          : 'The backend service is unavailable or ran into an error. Please try again later.'
        : res.status === 404
          ? 'Not found.'
          : `Request failed (${res.status}).`;
    throw new ApiError(extractDetail(body, fallback), res.status);
  }
  return body as T;
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

let cachedUser: User | null = null;

export async function login(email: string, password: string): Promise<User> {
  const token = MOCK_AUTH
    ? await mock.login(email, password)
    : await request<{ access_token: string; token_type: 'bearer'; expires_at: string }>('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      });
  saveToken(token);
  return getCurrentUser();
}

export async function register(email: string, password: string): Promise<User> {
  if (MOCK_AUTH) return mock.register(email, password);
  return request<User>('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
}

export async function getCurrentUser(): Promise<User> {
  const user = MOCK_AUTH ? await mock.getCurrentUser(getToken()) : await request<User>('/api/auth/me');
  cachedUser = user;
  return user;
}

export async function logout(): Promise<void> {
  try {
    if (MOCK_AUTH) await mock.logout(getToken());
    else if (getToken()) await request<void>('/api/auth/logout', { method: 'POST' });
  } catch {
    // Log out locally even if the server call fails.
  } finally {
    clearToken();
    cachedUser = null;
    clearCaches();
  }
}

/** Owner key used to scope mock meeting data per user (id + email survives DB resets). */
function mockOwner(): string {
  return cachedUser ? `${cachedUser.id}:${cachedUser.email}` : 'anonymous';
}

// ---------------------------------------------------------------------------
// Caches (live mode)
//
// module2 has no GET /api/meetings/{id} or status field, so the meeting page
// derives both from the list and the transcript. The transcript is also the
// input to the browser-side AI, so it is cached rather than refetched per tab.
// ---------------------------------------------------------------------------

const transcriptCache = new Map<string, Promise<Transcript>>();
const analysisCache = new Map<string, mock.Analysis>();

function clearCaches() {
  transcriptCache.clear();
  analysisCache.clear();
}

function liveTranscript(id: Id): Promise<Transcript> {
  const key = String(id);
  let pending = transcriptCache.get(key);
  if (!pending) {
    pending = request<Transcript>(`/api/meetings/${id}/transcript`);
    transcriptCache.set(key, pending);
    pending.catch(() => transcriptCache.delete(key));
  }
  return pending;
}

/** module2 returns 409 from GET .../transcript until the transcript has been processed. */
async function liveStatus(id: Id): Promise<MeetingStatus> {
  try {
    await liveTranscript(id);
    return 'completed';
  } catch (err) {
    if (err instanceof ApiError && err.status === 409) return 'uploaded';
    throw err;
  }
}

async function liveAnalysis(id: Id): Promise<mock.Analysis> {
  const key = String(id);
  const cached = analysisCache.get(key);
  if (cached) return cached;
  const analysis = mock.analyseSegments(segmentsOf(await liveTranscript(id)));
  analysisCache.set(key, analysis);
  return analysis;
}

/** Multipart POST via XHR so upload progress can be reported. */
function uploadForm<T>(path: string, form: FormData, onProgress?: (percent: number) => void): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', path);
    const token = getToken();
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onerror = () => reject(new ApiError('Upload failed. Please check your connection.', 0));
    xhr.onload = () => {
      let body: unknown = undefined;
      try {
        body = xhr.responseText ? JSON.parse(xhr.responseText) : undefined;
      } catch {
        body = xhr.responseText;
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(body as T);
      } else {
        if (xhr.status === 401) handleUnauthorized(path);
        reject(new ApiError(extractDetail(body, `Upload failed (${xhr.status}).`), xhr.status));
      }
    };
    xhr.send(form);
  });
}

// ---------------------------------------------------------------------------
// Meetings
// ---------------------------------------------------------------------------

export function getMeetings(): Promise<Meeting[]> {
  if (MOCK_MEETINGS) return mock.getMeetings(mockOwner());
  return request<Meeting[]>('/api/meetings');
}

export async function getMeeting(id: Id): Promise<Meeting> {
  if (MOCK_MEETINGS) return mock.getMeeting(mockOwner(), id);
  const meeting = (await getMeetings()).find((m) => String(m.id) === String(id));
  if (!meeting) throw new ApiError('Meeting not found.', 404);
  return { ...meeting, status: await liveStatus(id) };
}

/** Creates a meeting and stores its transcript file in one call. */
export async function uploadMeeting(
  title: string,
  file: File,
  onProgress?: (percent: number) => void,
): Promise<Meeting> {
  if (MOCK_MEETINGS) return mock.uploadMeeting(mockOwner(), title, file, onProgress);
  const form = new FormData();
  form.append('title', title);
  form.append('file', file);
  const meeting = await uploadForm<Meeting>('/api/meetings/upload', form, onProgress);
  return { ...meeting, status: 'uploaded' };
}

export function deleteMeeting(id: Id): Promise<void> {
  if (MOCK_MEETINGS) return mock.deleteMeeting(mockOwner(), id);
  return Promise.reject(new ApiError('Deleting meetings is not supported by the backend yet.', 501));
}

// ---------------------------------------------------------------------------
// Transcript
// ---------------------------------------------------------------------------

export function getTranscript(id: Id): Promise<Transcript> {
  if (MOCK_MEETINGS) return mock.getTranscript(mockOwner(), id);
  return liveTranscript(id);
}

/**
 * Starts analysis. In module2 this parses the uploaded file into speaker
 * sections synchronously, and fails with 422 if a line isn't "Speaker: text".
 */
export async function processMeeting(id: Id): Promise<Meeting> {
  if (MOCK_MEETINGS) return mock.processMeeting(mockOwner(), id);
  const key = String(id);
  transcriptCache.delete(key);
  analysisCache.delete(key);
  const transcript = await request<Transcript>(`/api/meetings/${id}/transcript/process`, { method: 'POST' });
  transcriptCache.set(key, Promise.resolve(transcript));
  return getMeeting(id);
}

// ---------------------------------------------------------------------------
// AI processing outputs
// ---------------------------------------------------------------------------

// Accepts both {"action_items": [...]} (module3's shape) and a bare list,
// and fills in ids when the backend doesn't send them.
function listOf<T extends { id?: number | string }>(body: unknown, key: string): T[] {
  const items = (Array.isArray(body) ? body : ((body as Record<string, unknown> | null)?.[key] ?? [])) as T[];
  return items.map((item, i) => ({ ...item, id: item.id ?? i + 1 }));
}

export async function getSummary(id: Id): Promise<Summary> {
  if (MOCK_MEETINGS) return mock.getSummary(mockOwner(), id);
  if (MOCK_AI) return (await liveAnalysis(id)).summary;
  return request<Summary>(`/api/meetings/${id}/summary`);
}

export async function getActionItems(id: Id): Promise<ActionItem[]> {
  if (MOCK_MEETINGS) return mock.getActionItems(mockOwner(), id);
  if (MOCK_AI) return (await liveAnalysis(id)).action_items;
  return listOf<ActionItem>(await request<unknown>(`/api/meetings/${id}/action-items`), 'action_items');
}

export async function getDecisions(id: Id): Promise<Decision[]> {
  if (MOCK_MEETINGS) return mock.getDecisions(mockOwner(), id);
  if (MOCK_AI) return (await liveAnalysis(id)).decisions;
  return listOf<Decision>(await request<unknown>(`/api/meetings/${id}/decisions`), 'decisions');
}

// ---------------------------------------------------------------------------
// Chat / Q&A
// ---------------------------------------------------------------------------

export async function askQuestion(id: Id, question: string): Promise<ChatResponse> {
  if (MOCK_MEETINGS) return mock.askQuestion(mockOwner(), id, question);
  if (MOCK_AI) {
    const [transcript, analysis] = await Promise.all([liveTranscript(id), liveAnalysis(id)]);
    return mock.answerQuestion(question, segmentsOf(transcript), analysis.summary);
  }
  return request<ChatResponse>(`/api/meetings/${id}/chat`, {
    method: 'POST',
    body: JSON.stringify({ question }),
  });
}
