// Client-side transcript helpers.
//
// Splits raw transcript text into segments (one per speaker turn / line) so
// the transcript can be displayed with speakers and timestamps, and so chat
// citations can be located inside it. Handles common formats:
//
//   [00:01:23] Alice: text          00:01:23 Alice: text
//   Alice (00:01:23): text          Alice: text
//   WebVTT / SRT cue blocks         plain paragraphs

import type { Citation, TranscriptSegment } from './types';

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

function normaliseText(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9 ]+/g, ' ').replace(/\s+/g, ' ').trim();
}

/** Best-effort lookup of the transcript segment a citation refers to. */
export function findSegmentForCitation(
  segments: TranscriptSegment[],
  citation: Citation,
): TranscriptSegment | undefined {
  const byId = segments.find((s) => s.id === citation.chunk_id);
  if (byId) return byId;

  if (citation.start_time) {
    const t = normaliseTime(citation.start_time);
    const byTime = segments.find((s) => s.start_time === t);
    if (byTime) return byTime;
  }

  const needle = normaliseText(citation.text).slice(0, 60);
  if (!needle) return undefined;
  return segments.find((s) => {
    const hay = normaliseText(s.text);
    return hay.length > 0 && (hay.includes(needle) || needle.includes(hay.slice(0, 60)));
  });
}
