// Client-side transcript helpers.
//
// Splits raw transcript text into segments (one per speaker turn / line) so
// the transcript can be displayed with speakers and timestamps, and so chat
// citations can be located inside it. Handles common formats:
//
//   [00:01:23] Alice: text          00:01:23 Alice: text
//   Alice (00:01:23): text          Alice: text
//   WebVTT / SRT cue blocks         plain paragraphs

import type { Citation, Transcript, TranscriptSegment } from './types';

const TIME = String.raw`\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d{1,3})?`;
const CUE_TIMING = new RegExp(`^(${TIME})\\s*-->\\s*(${TIME})`);
const LEADING_TIME = new RegExp(`^[\\[(]?(${TIME})[\\])]?\\s*[-–]?\\s*`);
const SPEAKER_WITH_TIME = new RegExp(`^([^:\\[\\]()]{1,40}?)\\s*[\\[(](${TIME})[\\])]\\s*:?\\s*(.*)$`);
const SPEAKER = /^([A-Z][\w .'-]{0,39}?):\s+(.*)$/;
const VTT_VOICE = /^<v\s+([^>]+)>(.*?)(?:<\/v>)?$/;

function normaliseTime(t: string): string {
  return t.replace(/[.,]\d+$/, '');
}

export function parseTranscript(raw: string): TranscriptSegment[] {
  const lines = raw.replace(/\r\n?/g, '\n').split('\n');
  const segments: TranscriptSegment[] = [];
  let cueTime: string | undefined;

  const push = (text: string, speaker?: string, start_time?: string) => {
    const clean = text.trim();
    if (!clean) return;
    const index = segments.length;
    segments.push({ id: `seg-${index}`, index, speaker: speaker?.trim(), start_time, text: clean });
  };

  let canContinue = false; // a blank line ends the current speaker's turn

  for (const rawLine of lines) {
    let line = rawLine.trim();
    if (!line) {
      canContinue = false;
      continue;
    }
    if (line === 'WEBVTT' || /^NOTE\b/.test(line) || /^\d+$/.test(line)) continue;
    const continues = canContinue;
    canContinue = true;

    const cue = line.match(CUE_TIMING);
    if (cue) {
      cueTime = normaliseTime(cue[1]);
      continue;
    }

    let time = cueTime;
    cueTime = undefined;

    const voice = line.match(VTT_VOICE);
    if (voice) {
      push(voice[2], voice[1], time);
      continue;
    }

    const lead = line.match(LEADING_TIME);
    if (lead) {
      time = normaliseTime(lead[1]);
      line = line.slice(lead[0].length);
    }

    const withTime = line.match(SPEAKER_WITH_TIME);
    if (withTime) {
      push(withTime[3], withTime[1], normaliseTime(withTime[2]));
      continue;
    }

    const speaker = line.match(SPEAKER);
    if (speaker) {
      push(speaker[2], speaker[1], time);
      continue;
    }

    // Continuation of the previous speaker's turn (no new speaker/time).
    const prev = segments[segments.length - 1];
    if (prev && !time && prev.speaker && continues) {
      prev.text = `${prev.text} ${line}`;
    } else {
      push(line, undefined, time);
    }
  }

  return segments;
}

const FILLER_WORDS = new Set([
  'the', 'and', 'that', 'this', 'with', 'for', 'from', 'have', 'will', 'would',
  'could', 'should', 'you', 'your', 'our', 'are', 'was', 'were', 'been', 'has',
  'had', 'not', 'but', 'they', 'their', 'them', 'there', 'then', 'than', 'into',
  'about', 'what', 'when', 'where', 'which', 'who', 'whom', 'how', 'why', 'can',
  'may', 'might', 'must', 'shall', 'just', 'also', 'only', 'some', 'any', 'all',
]);

/** Meaningful words in a quote, ignoring the "Speaker:" prefix and filler. */
function citationTokens(text: string): string[] {
  const body = text.replace(/^[A-Z][\w .'-]{0,39}:\s*/, '');
  const tokens = body.toLowerCase().match(/[a-z0-9]+/g) ?? [];
  return [...new Set(tokens.filter((t) => t.length > 2 && !FILLER_WORDS.has(t)))];
}

/**
 * Best-effort lookup of the transcript segment a citation refers to.
 *
 * Exact section ids win, then text similarity (with a timestamp tie-breaker),
 * then a matching timestamp alone. The text fallback scores token overlap
 * rather than matching an arbitrary 60-character substring: a quote that only
 * shares one generic word must not send the reader to an unrelated part of the
 * transcript, so it returns undefined instead.
 */
export function findSegmentForCitation(
  segments: TranscriptSegment[],
  citation: Citation,
): TranscriptSegment | undefined {
  const byId = segments.find((s) => s.id === citation.chunk_id);
  if (byId) return byId;

  const startTime = citation.start_time ? normaliseTime(citation.start_time) : undefined;
  const needle = citationTokens(citation.text);

  let best: TranscriptSegment | undefined;
  let bestScore = 0;
  for (const segment of segments) {
    const hay = new Set(citationTokens(segment.text));
    if (hay.size === 0) continue;

    const overlap = needle.reduce((count, token) => count + (hay.has(token) ? 1 : 0), 0);
    if (overlap < 2) continue;

    const coverage = overlap / needle.length;
    if (coverage < 0.5) continue;

    // A matching timestamp is a tie-breaker, not proof: the model can quote
    // the right passage while naming the wrong time.
    const score =
      coverage +
      (overlap / hay.size) * 0.05 +
      (startTime && normaliseTime(segment.start_time ?? '') === startTime ? 0.1 : 0);
    if (score > bestScore) {
      best = segment;
      bestScore = score;
    }
  }

  if (best) return best;

  // No usable text: fall back to the timestamp if it exists.
  if (startTime) {
    return segments.find((s) => normaliseTime(s.start_time ?? '') === startTime);
  }

  return undefined;
}

/** Segments for display: module2's parsed sections when present, else parse the raw text. */
export function segmentsOf(transcript: Transcript): TranscriptSegment[] {
  if (transcript.sections) {
    return transcript.sections.map((s, index) => ({
      id: s.section_id,
      index,
      speaker: s.speaker_name,
      start_time: s.timestamp ?? undefined,
      text: s.text,
    }));
  }
  return parseTranscript(transcript.raw_text ?? '');
}
