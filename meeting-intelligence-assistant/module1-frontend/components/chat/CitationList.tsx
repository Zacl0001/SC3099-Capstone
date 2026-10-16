import type { Citation as CitationType } from '@/lib/types';
import Citation from './Citation';

interface CitationListProps {
  citations: CitationType[];
  onView?: (citation: CitationType) => void;
}

export default function CitationList({ citations, onView }: CitationListProps) {
  if (citations.length === 0) return null;
  return (
    <div className="mt-3">
      <p className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">Sources</p>
      <ul className="grid gap-2">
        {citations.map((c, i) => (
          <li key={`${c.chunk_id}-${i}`}>
            <Citation index={i + 1} citation={c} onView={onView} />
          </li>
        ))}
      </ul>
    </div>
  );
}
