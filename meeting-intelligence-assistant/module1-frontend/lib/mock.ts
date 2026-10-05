// In-browser mock of the backend API.
//
// Used when NEXT_PUBLIC_MOCK_AUTH / NEXT_PUBLIC_MOCK_MEETINGS are enabled so the
// frontend can be developed and demoed before module2/3/4 are ready.
// Data lives in localStorage. The "AI" here is simple keyword heuristics -
// it only exists to exercise the UI with realistic-looking data.

import { ApiError } from './errors';
import { parseTranscript } from './transcript';
import type {
  ActionItem,
  ChatResponse,
  Citation,
  Decision,
  Meeting,
  MeetingCreate,
  Summary,
  TokenResponse,
  Transcript,
  TranscriptSegment,
  User,
} from './types';

type Id = number | string;

const PROCESSING_MS = 4000;

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

function read<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function write(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    throw new ApiError('Browser storage is full or unavailable.', 507);
  }
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

interface MockUser extends User {
  password_hash: string;
}
type Sessions = Record<string, { user_id: number; expires_at: string }>;

const USERS_KEY = 'mia.mock.users';
const SESSIONS_KEY = 'mia.mock.sessions';

async function hash(password: string): Promise<string> {
  if (!globalThis.crypto?.subtle) return password;
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(password));
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, '0')).join('');
}

export async function register(email: string, password: string): Promise<User> {
  await sleep(300);
  const normalised = email.trim().toLowerCase();
  if (password.length < 8) throw new ApiError('Password must be at least 8 characters', 422);
  const users = read<MockUser[]>(USERS_KEY, []);
  if (users.some((u) => u.email === normalised)) throw new ApiError('Email already registered', 409);
  const user: MockUser = {
    id: users.reduce((max, u) => Math.max(max, u.id), 0) + 1,
    email: normalised,
    password_hash: await hash(password),
  };
  write(USERS_KEY, [...users, user]);
  return { id: user.id, email: user.email };
}

export async function login(email: string, password: string): Promise<TokenResponse> {
  await sleep(300);
  const users = read<MockUser[]>(USERS_KEY, []);
  const user = users.find((u) => u.email === email.trim().toLowerCase());
  if (!user || user.password_hash !== (await hash(password))) {
    throw new ApiError('Invalid email or password', 401);
  }
  const token = crypto.randomUUID();
  const expires_at = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString();
  write(SESSIONS_KEY, { ...read<Sessions>(SESSIONS_KEY, {}), [token]: { user_id: user.id, expires_at } });
  return { access_token: token, token_type: 'bearer', expires_at };
}

export async function getCurrentUser(token: string | null): Promise<User> {
  const session = token ? read<Sessions>(SESSIONS_KEY, {})[token] : undefined;
  const user = session && read<MockUser[]>(USERS_KEY, []).find((u) => u.id === session.user_id);
  if (!user || new Date(session.expires_at).getTime() <= Date.now()) {
    throw new ApiError('Invalid or expired session', 401);
  }
  return { id: user.id, email: user.email };
}

export async function logout(token: string | null): Promise<void> {
  if (!token) return;
  const sessions = read<Sessions>(SESSIONS_KEY, {});
  delete sessions[token];
  write(SESSIONS_KEY, sessions);
}

// ---------------------------------------------------------------------------
// Meetings
// ---------------------------------------------------------------------------

interface MockMeeting extends Meeting {
  id: number;
  transcript?: Transcript;
  processing_started_at?: number;
  summary?: Summary;
  action_items?: ActionItem[];
  decisions?: Decision[];
}

const meetingsKey = (owner: string) => `mia.mock.meetings.${owner}`;

function loadMeetings(owner: string): MockMeeting[] {
  const meetings = read<MockMeeting[]>(meetingsKey(owner), []);
  // Finish any "processing" jobs whose simulated time has elapsed.
  let changed = false;
  for (const m of meetings) {
    if (m.status === 'processing' && m.processing_started_at && Date.now() - m.processing_started_at > PROCESSING_MS) {
      Object.assign(m, analyse(m.transcript?.raw_text ?? ''));
      m.status = 'completed';
      m.updated_at = new Date().toISOString();
      changed = true;
    }
  }
  if (changed) write(meetingsKey(owner), meetings);
  return meetings;
}

function findMeeting(meetings: MockMeeting[], id: Id): MockMeeting {
  const meeting = meetings.find((m) => String(m.id) === String(id));
  if (!meeting) throw new ApiError('Meeting not found', 404);
  return meeting;
}

function toMeeting(m: MockMeeting): Meeting {
  return {
    id: m.id,
    title: m.title,
    description: m.description,
    status: m.status,
    created_at: m.created_at,
    updated_at: m.updated_at,
    transcript_file_name: m.transcript?.file_name ?? null,
    error_message: m.error_message,
  };
}

function requireCompleted(m: MockMeeting): void {
  if (m.status !== 'completed') throw new ApiError('Meeting has not finished processing', 409);
}

export async function getMeetings(owner: string): Promise<Meeting[]> {
  await sleep(150);
  return loadMeetings(owner)
    .map(toMeeting)
    .sort((a, b) => b.created_at.localeCompare(a.created_at));
}

export async function getMeeting(owner: string, id: Id): Promise<Meeting> {
  await sleep(100);
  return toMeeting(findMeeting(loadMeetings(owner), id));
}

export async function createMeeting(owner: string, data: MeetingCreate): Promise<Meeting> {
  await sleep(200);
  const meetings = loadMeetings(owner);
  const now = new Date().toISOString();
  const meeting: MockMeeting = {
    id: meetings.reduce((max, m) => Math.max(max, m.id), 0) + 1,
    title: data.title,
    description: data.description ?? null,
    status: 'uploaded',
    created_at: now,
    updated_at: now,
  };
  write(meetingsKey(owner), [...meetings, meeting]);
  return toMeeting(meeting);
}

export async function deleteMeeting(owner: string, id: Id): Promise<void> {
  await sleep(150);
  const meetings = loadMeetings(owner);
  findMeeting(meetings, id);
  write(
    meetingsKey(owner),
    meetings.filter((m) => String(m.id) !== String(id)),
  );
}

export async function uploadTranscript(
  owner: string,
  id: Id,
  file: File,
  onProgress?: (percent: number) => void,
): Promise<Transcript> {
  for (const p of [20, 45, 70, 90]) {
    onProgress?.(p);
    await sleep(120);
  }
  const raw_text = await file.text();
  if (!raw_text.trim()) throw new ApiError('Transcript file is empty', 422);

  const meetings = loadMeetings(owner);
  const meeting = findMeeting(meetings, id);
  const transcript: Transcript = {
    meeting_id: meeting.id,
    file_name: file.name,
    raw_text,
    created_at: new Date().toISOString(),
  };
  Object.assign(meeting, {
    transcript,
    status: 'uploaded',
    summary: undefined,
    action_items: undefined,
    decisions: undefined,
    updated_at: transcript.created_at,
  });
  write(meetingsKey(owner), meetings);
  onProgress?.(100);
  return transcript;
}

export async function getTranscript(owner: string, id: Id): Promise<Transcript> {
  await sleep(100);
  const meeting = findMeeting(loadMeetings(owner), id);
  if (!meeting.transcript) throw new ApiError('No transcript uploaded for this meeting', 404);
  return meeting.transcript;
}

export async function processMeeting(owner: string, id: Id): Promise<Meeting> {
  await sleep(200);
  const meetings = loadMeetings(owner);
  const meeting = findMeeting(meetings, id);
  if (!meeting.transcript) throw new ApiError('Upload a transcript before processing', 409);
  meeting.status = 'processing';
  meeting.processing_started_at = Date.now();
  meeting.error_message = null;
  meeting.updated_at = new Date().toISOString();
  write(meetingsKey(owner), meetings);
  return toMeeting(meeting);
}

export async function getSummary(owner: string, id: Id): Promise<Summary> {
  await sleep(250);
  const meeting = findMeeting(loadMeetings(owner), id);
  requireCompleted(meeting);
  return meeting.summary!;
}

export async function getActionItems(owner: string, id: Id): Promise<ActionItem[]> {
  await sleep(250);
  const meeting = findMeeting(loadMeetings(owner), id);
  requireCompleted(meeting);
  return meeting.action_items ?? [];
}

export async function getDecisions(owner: string, id: Id): Promise<Decision[]> {
  await sleep(250);
  const meeting = findMeeting(loadMeetings(owner), id);
  requireCompleted(meeting);
  return meeting.decisions ?? [];
}

export async function askQuestion(owner: string, id: Id, question: string): Promise<ChatResponse> {
  await sleep(700);
  const meeting = findMeeting(loadMeetings(owner), id);
  if (!meeting.transcript) throw new ApiError('No transcript uploaded for this meeting', 409);
  return answer(question, parseTranscript(meeting.transcript.raw_text), meeting.summary);
}

// ---------------------------------------------------------------------------
// Fake "AI": keyword heuristics over the transcript
// ---------------------------------------------------------------------------

const STOPWORDS = new Set(
  `a about above after again against all also am an and any are as at be because been before being below between both
  but by can could did do does doing down during each few for from further had has have having he her here hers him his
  how i i'll i'm if in into is it it's its just let's me more most my no nor not now of off on once only or other our ours
  out over own same she should so some such than that that's the their them then there these they this those through to
  too under until up very was we we'll we're were what when where which while who whom why will with would you your yes
  okay ok yeah thanks thank everyone morning good great think need needs going get got one two three last next well really
  said say says much many us did does done make sure still about want wants`.split(/\s+/),
);

const DAY = String.raw`(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|tomorrow|tonight)`;
const MONTH = String.raw`(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*`;
const DEADLINE_RE = new RegExp(
  String.raw`\b(?:by|before|due)\s+((?:next |this |the )?(?:${DAY}|end of (?:the )?\w+|\d{1,2}(?:st|nd|rd|th)?(?: (?:of )?${MONTH})?|${MONTH} \d{1,2}(?:st|nd|rd|th)?))\b`,
  'i',
);
const COMMITMENT_RE =
  /\b(?:I will|I'll|we'll|will (?:send|draft|prepare|update|share|finish|complete|create|review|write|follow up|ask|set up|schedule|fix|investigate|check|book|organi[sz]e|circulate))\b|\b(?:action item|to-?do)\b/i;
const DECISION_RE =
  /\b(?:decided|decision is|final decision|agreed|we agree|let's go with|go ahead with|approved|we will go with)\b/i;
const NON_NAMES = new Set(['I', 'We', 'It', 'That', 'This', 'They', 'Then', 'Which', 'Who', 'There', 'He', 'She', 'You']);

function sentencesOf(text: string): string[] {
  return text.split(/(?<=[.!?])\s+/).map((s) => s.trim()).filter(Boolean);
}

function wordsOf(text: string): string[] {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9' ]+/g, ' ')
    .split(/\s+/)
    .filter((w) => w.length > 2 && !STOPWORDS.has(w));
}

function stem(w: string): string {
  return w.replace(/'s$/, '').replace(/(ing|ed|es|s)$/, '');
}

function capitalise(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function stripFiller(s: string): string {
  return s.replace(/^(?:(?:yes|okay|ok|so|and|great|also|then|right|alright)[,.]?\s+)+/i, '');
}

/** A segment as a readable key point: whole turn if short, else its most informative sentences. */
function keyPoint(text: string, topicWords: Set<string>): string {
  if (text.length <= 220) return text;
  return sentencesOf(text)
    .map((sentence, i) => ({ sentence, i, score: wordsOf(sentence).filter((w) => topicWords.has(w)).length }))
    .sort((a, b) => b.score - a.score || b.sentence.length - a.sentence.length)
    .slice(0, 2)
    .sort((a, b) => a.i - b.i)
    .map((x) => x.sentence)
    .join(' ');
}

function extractTopics(segments: TranscriptSegment[]): string[] {
  const speakers = new Set(segments.map((s) => s.speaker?.toLowerCase()).filter(Boolean));
  const uni = new Map<string, number>();
  const bi = new Map<string, number>();
  for (const seg of segments) {
    for (const sentence of sentencesOf(seg.text)) {
      const words = wordsOf(sentence).filter((w) => !speakers.has(w) && !/^\d/.test(w));
      words.forEach((w, i) => {
        if (w.length >= 4) uni.set(w, (uni.get(w) ?? 0) + 1);
        if (i > 0) {
          const pair = `${words[i - 1]} ${w}`;
          bi.set(pair, (bi.get(pair) ?? 0) + 1);
        }
      });
    }
  }
  const topics: string[] = [];
  const covered = new Set<string>();
  for (const [pair] of [...bi].filter(([, n]) => n >= 2).sort((a, b) => b[1] - a[1])) {
    if (topics.length >= 3) break;
    topics.push(pair);
    pair.split(' ').forEach((w) => covered.add(w));
  }
  for (const [w] of [...uni].sort((a, b) => b[1] - a[1])) {
    if (topics.length >= 5) break;
    if (!covered.has(w)) topics.push(w);
  }
  return topics.map(capitalise);
}

function analyse(raw: string): Pick<MockMeeting, 'summary' | 'action_items' | 'decisions'> {
  const segments = parseTranscript(raw);
  const action_items: ActionItem[] = [];
  const decisions: Decision[] = [];
  const used = new Set<string>();

  for (const seg of segments) {
    for (const sentence of sentencesOf(seg.text)) {
      const wordCount = sentence.split(/\s+/).length;
      if (wordCount < 4 || sentence.endsWith('?')) continue;

      if (DECISION_RE.test(sentence) && decisions.length < 8) {
        decisions.push({
          id: decisions.length + 1,
          decision: capitalise(stripFiller(wordCount >= 6 ? sentence : seg.text)),
          evidence: seg.text,
          timestamp: seg.start_time ?? null,
        });
        used.add(seg.id);
      } else if (COMMITMENT_RE.test(sentence) && action_items.length < 10) {
        const named = sentence.match(/\b([A-Z][a-z]+) will\b/);
        const assignee = named && !NON_NAMES.has(named[1]) ? named[1] : (seg.speaker ?? null);
        const task = capitalise(
          stripFiller(sentence).replace(/^(?:I|we|[A-Z][a-z]+)(?:\s+will|'ll)\s+(?:also\s+)?/i, ''),
        );
        action_items.push({
          id: action_items.length + 1,
          task,
          assignee,
          deadline: sentence.match(DEADLINE_RE)?.[1] ?? null,
          status: 'open',
          evidence: seg.text,
          timestamp: seg.start_time ?? null,
        });
        used.add(seg.id);
      }
    }
  }

  const topics = extractTopics(segments);
  const topicWords = new Set(topics.flatMap((t) => t.toLowerCase().split(' ')));
  const keyPoints = segments
    .filter((s) => !used.has(s.id) && s.text.split(/\s+/).length >= 8)
    .map((s) => ({ s, score: wordsOf(s.text).filter((w) => topicWords.has(w)).length }))
    .sort((a, b) => b.score - a.score)
    .slice(0, 4)
    .sort((a, b) => a.s.index - b.s.index)
    .map(({ s }) => `${s.speaker ? `${s.speaker}: ` : ''}${keyPoint(s.text, topicWords)}`);

  const speakers = [...new Set(segments.map((s) => s.speaker).filter(Boolean))] as string[];
  const who =
    speakers.length === 0
      ? 'The participants'
      : speakers.length === 1
        ? speakers[0]
        : `${speakers.slice(0, -1).join(', ')} and ${speakers[speakers.length - 1]}`;
  const about = topics.slice(0, 3).map((t) => t.toLowerCase());
  let summary =
    `${who} met to discuss ${about.length ? about.join(', ') : 'the items on the agenda'}. ` +
    `The discussion produced ${decisions.length} decision${decisions.length === 1 ? '' : 's'} and ` +
    `${action_items.length} action item${action_items.length === 1 ? '' : 's'}.`;
  if (decisions[0]) summary += ` The main outcome: ${decisions[0].decision}`;

  return { summary: { summary, key_points: keyPoints, topics }, action_items, decisions };
}

function answer(question: string, segments: TranscriptSegment[], summary?: Summary): ChatResponse {
  const qWords = [...new Set(wordsOf(question).map(stem))];
  const scored = segments
    .map((s) => {
      const segWords = new Set(wordsOf(s.text).map(stem));
      let score = qWords.filter((w) => segWords.has(w)).length;
      if (s.speaker && question.toLowerCase().includes(s.speaker.toLowerCase())) score += 1;
      return { s, score };
    })
    .filter((x) => x.score > 0)
    .sort((a, b) => b.score - a.score || a.s.index - b.s.index)
    .slice(0, 3)
    .sort((a, b) => a.s.index - b.s.index);

  if (scored.length === 0) {
    if (/summar|overview|recap|about/i.test(question) && summary) {
      return { answer: summary.summary, citations: [] };
    }
    return {
      answer: "I couldn't find anything in this meeting's transcript related to that question. Try rephrasing or asking about a specific topic or person.",
      citations: [],
    };
  }

  const citations: Citation[] = scored.map(({ s }) => ({
    chunk_id: s.id,
    start_time: s.start_time ?? null,
    end_time: null,
    speaker: s.speaker ?? null,
    text: s.text,
  }));
  const lines = scored.map(({ s }, i) => {
    const quote = sentencesOf(s.text).slice(0, 2).join(' ');
    return `${s.speaker ? `${s.speaker} said` : 'The transcript says'}: "${quote}" [${i + 1}]`;
  });
  return { answer: `Here is what the meeting covered on that:\n\n${lines.join('\n\n')}`, citations };
}
