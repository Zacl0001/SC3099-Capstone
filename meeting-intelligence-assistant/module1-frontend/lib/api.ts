// Centralised API communication.
//
// Every backend call goes through this file. Requests use relative /api/*
// URLs which next.config.js proxies to module2-backend.
//
// While backend endpoints are still being built, NEXT_PUBLIC_MOCK_AUTH /
// NEXT_PUBLIC_MOCK_MEETINGS route calls to lib/mock.ts instead (see config.ts).
//
// Endpoints used:
//   POST   /api/auth/register                 RegisterRequest -> User
//   POST   /api/auth/login                    LoginRequest    -> TokenResponse
//   GET    /api/auth/me                                       -> User
//   POST   /api/auth/logout                                   -> 204
//   GET    /api/meetings                                      -> Meeting[]
//   POST   /api/meetings                      MeetingCreate   -> Meeting
//   GET    /api/meetings/{id}                                 -> Meeting
//   DELETE /api/meetings/{id}                                 -> 204
//   POST   /api/meetings/{id}/transcript      multipart "file" -> Transcript
//   GET    /api/meetings/{id}/transcript                      -> Transcript
//   POST   /api/meetings/{id}/process                         -> Meeting
//   GET    /api/meetings/{id}/summary                         -> Summary
//   GET    /api/meetings/{id}/action-items                    -> ActionItem[]
//   GET    /api/meetings/{id}/decisions                       -> Decision[]
//   POST   /api/meetings/{id}/chat            ChatRequest     -> ChatResponse

import { clearToken, getToken, saveToken } from './auth';
import { MOCK_AUTH, MOCK_MEETINGS } from './config';
import { ApiError } from './errors';
import * as mock from './mock';
import type {
  ActionItem,
  ChatResponse,
  Decision,
  Meeting,
  MeetingCreate,
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
    const fallback =
      res.status >= 500
        ? 'The server ran into a problem. Please try again.'
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
  }
}

/** Owner key used to scope mock meeting data per user. */
function mockOwner(): string {
  return cachedUser ? String(cachedUser.id) : 'anonymous';
}

// ---------------------------------------------------------------------------
// Meetings
// ---------------------------------------------------------------------------

export function getMeetings(): Promise<Meeting[]> {
  if (MOCK_MEETINGS) return mock.getMeetings(mockOwner());
  return request<Meeting[]>('/api/meetings');
}

export function getMeeting(id: Id): Promise<Meeting> {
  if (MOCK_MEETINGS) return mock.getMeeting(mockOwner(), id);
  return request<Meeting>(`/api/meetings/${id}`);
}

export function createMeeting(data: MeetingCreate): Promise<Meeting> {
  if (MOCK_MEETINGS) return mock.createMeeting(mockOwner(), data);
  return request<Meeting>('/api/meetings', { method: 'POST', body: JSON.stringify(data) });
}

export function deleteMeeting(id: Id): Promise<void> {
  if (MOCK_MEETINGS) return mock.deleteMeeting(mockOwner(), id);
  return request<void>(`/api/meetings/${id}`, { method: 'DELETE' });
}

// ---------------------------------------------------------------------------
// Transcript
// ---------------------------------------------------------------------------

/** Uploads a transcript file. Uses XHR so upload progress can be reported. */
export function uploadTranscript(id: Id, file: File, onProgress?: (percent: number) => void): Promise<Transcript> {
  if (MOCK_MEETINGS) return mock.uploadTranscript(mockOwner(), id, file, onProgress);

  const path = `/api/meetings/${id}/transcript`;
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
        resolve(body as Transcript);
      } else {
        if (xhr.status === 401) handleUnauthorized(path);
        reject(new ApiError(extractDetail(body, `Upload failed (${xhr.status}).`), xhr.status));
      }
    };

    const form = new FormData();
    form.append('file', file);
    xhr.send(form);
  });
}

export function getTranscript(id: Id): Promise<Transcript> {
  if (MOCK_MEETINGS) return mock.getTranscript(mockOwner(), id);
  return request<Transcript>(`/api/meetings/${id}/transcript`);
}

// ---------------------------------------------------------------------------
// AI processing outputs
// ---------------------------------------------------------------------------

export function processMeeting(id: Id): Promise<Meeting> {
  if (MOCK_MEETINGS) return mock.processMeeting(mockOwner(), id);
  return request<Meeting>(`/api/meetings/${id}/process`, { method: 'POST' });
}

export function getSummary(id: Id): Promise<Summary> {
  if (MOCK_MEETINGS) return mock.getSummary(mockOwner(), id);
  return request<Summary>(`/api/meetings/${id}/summary`);
}

export function getActionItems(id: Id): Promise<ActionItem[]> {
  if (MOCK_MEETINGS) return mock.getActionItems(mockOwner(), id);
  return request<ActionItem[]>(`/api/meetings/${id}/action-items`);
}

export function getDecisions(id: Id): Promise<Decision[]> {
  if (MOCK_MEETINGS) return mock.getDecisions(mockOwner(), id);
  return request<Decision[]>(`/api/meetings/${id}/decisions`);
}

// ---------------------------------------------------------------------------
// Chat / Q&A
// ---------------------------------------------------------------------------

export function askQuestion(id: Id, question: string): Promise<ChatResponse> {
  if (MOCK_MEETINGS) return mock.askQuestion(mockOwner(), id, question);
  return request<ChatResponse>(`/api/meetings/${id}/chat`, {
    method: 'POST',
    body: JSON.stringify({ question }),
  });
}
