import { ClockIcon } from './Icons';

interface SourceButtonProps {
  timestamp?: string | null;
  onClick?: () => void;
  label?: string;
}

/** Small "jump to transcript" link shown next to AI-extracted items. */
export default function SourceButton({ timestamp, onClick, label = 'View in transcript' }: SourceButtonProps) {
  if (!onClick) {
    return timestamp ? (
      <span className="inline-flex items-center gap-1 font-mono text-xs text-slate-500">
        <ClockIcon className="size-3.5" />
        {timestamp}
      </span>
    ) : null;
  }
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-1 rounded text-xs font-medium text-brand-600 hover:text-brand-700 hover:underline"
    >
      <ClockIcon className="size-3.5" />
      {timestamp ? <span className="font-mono">{timestamp}</span> : null}
      <span>{label}</span>
    </button>
  );
}
