'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { inputClass } from '@/components/auth/FormField';
import { SearchIcon } from '@/components/common/Icons';
import type { TranscriptSegment } from '@/lib/types';

interface TranscriptViewerProps {
  segments: TranscriptSegment[];
  fileName?: string;
  /** Segment to scroll to and highlight (e.g. from a clicked citation). */
  highlightId?: string | null;
  /** Changes every time a jump is requested so the same segment can re-flash. */
  highlightNonce?: number;
}

const SPEAKER_COLOURS = [
  'text-brand-700',
  'text-emerald-700',
  'text-amber-700',
  'text-rose-700',
  'text-sky-700',
  'text-violet-700',
];

export default function TranscriptViewer({ segments, fileName, highlightId, highlightNonce }: TranscriptViewerProps) {
  const [query, setQuery] = useState('');
  const refs = useRef(new Map<string, HTMLLIElement>());

  const speakerColour = useMemo(() => {
    const speakers = [...new Set(segments.map((s) => s.speaker).filter(Boolean))] as string[];
    return new Map(speakers.map((s, i) => [s, SPEAKER_COLOURS[i % SPEAKER_COLOURS.length]]));
  }, [segments]);

  const q = query.trim().toLowerCase();
  const visible = q
    ? segments.filter((s) => s.text.toLowerCase().includes(q) || s.speaker?.toLowerCase().includes(q))
    : segments;

  useEffect(() => {
    if (!highlightId) return;
    refs.current.get(highlightId)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, [highlightId, highlightNonce]);

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex flex-wrap items-center gap-3 border-b border-slate-200 px-4 py-3">
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-slate-900">{fileName ?? 'Transcript'}</p>
          <p className="text-xs text-slate-500">
            {segments.length} segment{segments.length === 1 ? '' : 's'}
            {speakerColour.size > 0 && ` · ${speakerColour.size} speaker${speakerColour.size === 1 ? '' : 's'}`}
          </p>
        </div>
        <div className="relative w-full sm:w-64">
          <SearchIcon className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-slate-400" />
          <input
            type="search"
            aria-label="Search transcript"
            placeholder="Search transcript"
            className={`${inputClass} pl-9`}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
      </div>

      {visible.length === 0 ? (
        <p className="px-4 py-10 text-center text-sm text-slate-500">
          {segments.length === 0 ? 'The transcript is empty.' : `No lines match “${query}”.`}
        </p>
      ) : (
        <ol className="max-h-[65vh] divide-y divide-slate-100 overflow-y-auto">
          {visible.map((seg) => {
            const highlighted = seg.id === highlightId;
            return (
              <li
                key={highlighted ? `${seg.id}-${highlightNonce}` : seg.id}
                id={seg.id}
                ref={(el) => {
                  if (el) refs.current.set(seg.id, el);
                  else refs.current.delete(seg.id);
                }}
                className={`flex gap-4 px-4 py-3 text-sm ${
                  highlighted ? 'animate-highlight border-l-4 border-amber-400 bg-amber-50/60' : ''
                }`}
              >
                <span className="w-16 shrink-0 pt-0.5 font-mono text-xs text-slate-400">{seg.start_time ?? ''}</span>
                <div className="min-w-0 flex-1">
                  {seg.speaker && (
                    <p className={`mb-0.5 text-xs font-semibold ${speakerColour.get(seg.speaker) ?? ''}`}>{seg.speaker}</p>
                  )}
                  <p className="leading-relaxed whitespace-pre-wrap text-slate-700">{seg.text}</p>
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
