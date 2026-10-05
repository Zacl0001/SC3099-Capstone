// Build-time feature flags. See .env.example.
//
// NEXT_PUBLIC_* values are inlined by Next.js at build time, so they must be
// referenced literally (not via process.env[name]).

function flag(value: string | undefined, fallback: boolean): boolean {
  if (value === undefined || value === '') return fallback;
  return value.toLowerCase() === 'true';
}

export const MOCK_AUTH = flag(process.env.NEXT_PUBLIC_MOCK_AUTH, true);
export const MOCK_MEETINGS = flag(process.env.NEXT_PUBLIC_MOCK_MEETINGS, true) || MOCK_AUTH;

export const MAX_TRANSCRIPT_BYTES = 5 * 1024 * 1024;
export const TRANSCRIPT_EXTENSIONS = ['.txt', '.md', '.vtt', '.srt'];
