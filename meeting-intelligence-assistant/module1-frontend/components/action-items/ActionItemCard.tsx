import { CalendarIcon, CheckCircleIcon, CircleIcon, UserIcon } from '@/components/common/Icons';
import SourceButton from '@/components/common/SourceButton';
import type { ActionItem } from '@/lib/types';

interface ActionItemCardProps {
  item: ActionItem;
  onViewSource?: (item: ActionItem) => void;
}

export default function ActionItemCard({ item, onViewSource }: ActionItemCardProps) {
  const done = item.status === 'done' || item.status === 'completed';
  return (
    <article className="flex gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      {done ? (
        <CheckCircleIcon className="mt-0.5 size-5 shrink-0 text-emerald-600" />
      ) : (
        <CircleIcon className="mt-0.5 size-5 shrink-0 text-slate-300" />
      )}
      <span className="sr-only">{done ? 'Done:' : 'Open:'}</span>
      <div className="min-w-0 flex-1">
        <p className={`font-medium ${done ? 'text-slate-500 line-through' : 'text-slate-900'}`}>{item.task}</p>

        <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
          <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-0.5 text-slate-700">
            <UserIcon className="size-3.5" />
            {item.assignee || 'Unassigned'}
          </span>
          <span
            className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 ${
              item.deadline ? 'bg-amber-50 text-amber-800' : 'bg-slate-100 text-slate-500'
            }`}
          >
            <CalendarIcon className="size-3.5" />
            {item.deadline ? `Due ${item.deadline}` : 'No deadline'}
          </span>
          {(item.evidence || item.timestamp) && (
            <SourceButton
              timestamp={item.timestamp}
              onClick={onViewSource && item.evidence ? () => onViewSource(item) : undefined}
            />
          )}
        </div>

        {item.evidence && (
          <blockquote className="mt-3 border-l-2 border-slate-200 pl-3 text-sm text-slate-500 italic">
            “{item.evidence}”
          </blockquote>
        )}
      </div>
    </article>
  );
}
