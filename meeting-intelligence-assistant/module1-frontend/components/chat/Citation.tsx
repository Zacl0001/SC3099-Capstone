import { ClockIcon } from '@/components/common/Icons';
import type { Citation as CitationType } from '@/lib/types';

interface CitationProps {
  index: number;
  citation: CitationType;
  onView?: (citation: CitationType) => void;
}

/** One transcript reference supporting an answer, e.g. "[1] Alice · 00:31:20". */
export default function Citation({ index, citation, onView }: CitationProps) {
  const time = [citation.start_time, citation.end_time].filter(Boolean).join('–');
  const body = (
    <>
      <div className="flex items-center gap-2 text-xs">
        <span className="rounded bg-brand-100 px-1.5 py-0.5 font-semibold text-brand-700">[{index}]</span>
        {citation.speaker && <span className="font-medium text-slate-700">{citation.speaker}</span>}
        {time && (
          <span className="inline-flex items-center gap-1 font-mono text-slate-500">
            <ClockIcon className="size-3" />
            {time}
          </span>
        )}
      </div>
      <p className="mt-1 line-clamp-3 text-sm text-slate-600">{citation.text}</p>
    </>
  );

  if (!onView) return <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">{body}</div>;

  return (
    <button
      type="button"
      onClick={() => onView(citation)}
      title="View in transcript"
      className="block w-full rounded-lg border border-slate-200 bg-slate-50 p-3 text-left transition hover:border-brand-300 hover:bg-brand-50"
    >
      {body}
    </button>
  );
}
