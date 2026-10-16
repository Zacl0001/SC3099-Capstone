// Build-time feature flags. See .env.example.
//
// NEXT_PUBLIC_* values are inlined by Next.js at build time, so they must be
// referenced literally (not via process.env[name]).
//
// Defaults follow what module2-backend currently implements:
//   - auth (register, login, me, logout)                -> real backend
//   - meetings (upload, list) + transcripts (process, get) -> real backend
//   - summary, action items, decisions, chat           -> not in the backend yet; computed in
//                                                         the browser from the real transcript
// Flip a flag as each backend feature lands.

function flag(value: string | undefined, fallback: boolean): boolean {
  if (value === undefined || value === '') return fallback;
  return value.toLowerCase() === 'true';
}

/** Fake accounts in the browser. Forces the two flags below on (the backend rejects fake tokens). */
export const MOCK_AUTH = flag(process.env.NEXT_PUBLIC_MOCK_AUTH, false);
/** Fake meetings + transcripts in the browser (localStorage). Forces MOCK_AI on. */
export const MOCK_MEETINGS = flag(process.env.NEXT_PUBLIC_MOCK_MEETINGS, false) || MOCK_AUTH;
/** Compute summary / action items / decisions / chat in the browser from the transcript. */
export const MOCK_AI = flag(process.env.NEXT_PUBLIC_MOCK_AI, true) || MOCK_MEETINGS;

/** module2 has no DELETE /api/meetings/{id} yet. */
export const CAN_DELETE_MEETINGS = MOCK_MEETINGS;

// module2 extracts text from TXT, PDF and DOCX (max 10 MB). The browser mock can only read text files.
export const TRANSCRIPT_EXTENSIONS = MOCK_MEETINGS ? ['.txt', '.md', '.vtt', '.srt'] : ['.txt', '.pdf', '.docx'];
export const MAX_TRANSCRIPT_BYTES = (MOCK_MEETINGS ? 5 : 10) * 1024 * 1024;
