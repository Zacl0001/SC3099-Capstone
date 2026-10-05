// Frontend data contract.
//
// Field names are snake_case to match the FastAPI/Pydantic responses from
// module2-backend directly, so no mapping layer is needed. Anything marked
// optional is something the backend may not provide yet.

// ---------------------------------------------------------------------------
// Auth  (matches module2-backend/app/schemas/auth.py)
// ---------------------------------------------------------------------------

export interface User {
  id: number;
  email: string;
}

export interface RegisterRequest {
  email: string;
  password: string; // min 8 chars
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: 'bearer';
  expires_at: string; // ISO datetime
}

// ---------------------------------------------------------------------------
// Meetings
// ---------------------------------------------------------------------------

export type MeetingStatus = 'uploaded' | 'processing' | 'completed' | 'failed';

export interface Meeting {
  id: number | string;
  title: string;
  description?: string | null;
  status: MeetingStatus;
  created_at: string;
  updated_at?: string | null;
  transcript_file_name?: string | null;
  error_message?: string | null;
}

export interface MeetingCreate {
  title: string;
  description?: string;
}

// ---------------------------------------------------------------------------
// Transcript
// ---------------------------------------------------------------------------

export interface Transcript {
  meeting_id: number | string;
  file_name: string;
  raw_text: string;
  created_at: string;
}

/** One line/turn of a transcript. Parsed client-side from raw_text. */
export interface TranscriptSegment {
  id: string;
  index: number;
  speaker?: string;
  start_time?: string;
  text: string;
}

// ---------------------------------------------------------------------------
// AI outputs  (matches module3 schemas)
// ---------------------------------------------------------------------------

export interface Summary {
  summary: string;
  key_points: string[];
  topics?: string[];
}

export interface ActionItem {
  id: number | string;
  task: string;
  assignee?: string | null;
  deadline?: string | null;
  status?: 'open' | 'done' | string | null;
  evidence?: string | null;
  timestamp?: string | null;
}

export interface Decision {
  id: number | string;
  decision: string;
  evidence?: string | null;
  timestamp?: string | null;
}

// ---------------------------------------------------------------------------
// Chat / Q&A  (matches module4 schemas)
// ---------------------------------------------------------------------------

export interface ChatRequest {
  question: string;
}

export interface Citation {
  chunk_id: string;
  start_time?: string | null;
  end_time?: string | null;
  speaker?: string | null;
  text: string;
}

export interface ChatResponse {
  answer: string;
  citations: Citation[];
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  error?: boolean;
}
