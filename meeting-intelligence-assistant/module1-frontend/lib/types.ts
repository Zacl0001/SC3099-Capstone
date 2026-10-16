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

/** module2 MeetingResponse is {id, title, created_at}; the other fields are optional extras. */
export interface Meeting {
  id: number | string;
  title: string;
  description?: string | null;
  /** Not returned by module2's list endpoint; the frontend works it out on the meeting page. */
  status?: MeetingStatus;
  created_at: string;
  updated_at?: string | null;
  transcript_file_name?: string | null;
  error_message?: string | null;
}

// ---------------------------------------------------------------------------
// Transcript
// ---------------------------------------------------------------------------

/** One speaker turn as parsed by module2 (POST /api/meetings/{id}/transcript/process). */
export interface TranscriptSection {
  section_id: string;
  speaker_id: string;
  speaker_name: string;
  text: string;
  timestamp?: string | null;
}

/**
 * module2 returns {meeting_id, title, sections}. The browser mock stores the raw
 * text instead, which the frontend parses itself (lib/transcript.ts).
 */
export interface Transcript {
  meeting_id: number | string;
  title?: string;
  sections?: TranscriptSection[];
  file_name?: string;
  raw_text?: string;
  created_at?: string;
}

/** One line/turn of a transcript, from module2 sections or parsed from raw_text. */
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
