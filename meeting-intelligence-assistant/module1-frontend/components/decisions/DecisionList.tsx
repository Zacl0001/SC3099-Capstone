import EmptyState from '@/components/common/EmptyState';
import { GavelIcon } from '@/components/common/Icons';
import SourceButton from '@/components/common/SourceButton';
import type { Decision } from '@/lib/types';

interface DecisionListProps {
  decisions: Decision[];
  onViewSource?: (decision: Decision) => void;
}

export default function DecisionList({ decisions, onViewSource }: DecisionListProps) {
  if (decisions.length === 0) {
    return (
      <EmptyState
        icon={<GavelIcon />}
        title="No decisions found"
        description="No explicit decisions were identified in this meeting."
      />
    );
  }

  return (
    <ol className="space-y-3">
      {decisions.map((d, i) => (
        <li key={d.id} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex items-baseline justify-between gap-3">
            <p className="text-xs font-semibold tracking-wide text-brand-600 uppercase">Decision #{i + 1}</p>
            {(d.evidence || d.timestamp) && (
              <SourceButton
                timestamp={d.timestamp}
                label="Source"
                onClick={onViewSource && d.evidence ? () => onViewSource(d) : undefined}
              />
            )}
          </div>
          <p className="mt-1 font-medium text-slate-900">{d.decision}</p>
          {d.evidence && d.evidence !== d.decision && (
            <blockquote className="mt-3 border-l-2 border-slate-200 pl-3 text-sm text-slate-500 italic">
              “{d.evidence}”
            </blockquote>
          )}
        </li>
      ))}
    </ol>
  );
}
