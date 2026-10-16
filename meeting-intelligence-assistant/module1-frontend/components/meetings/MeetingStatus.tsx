import LoadingSpinner from '@/components/common/LoadingSpinner';
import type { MeetingStatus as Status } from '@/lib/types';

const styles: Record<Status, { label: string; className: string }> = {
  uploaded: { label: 'Uploaded', className: 'bg-slate-100 text-slate-700' },
  processing: { label: 'Processing', className: 'bg-blue-50 text-blue-700' },
  completed: { label: 'Completed', className: 'bg-emerald-50 text-emerald-700' },
  failed: { label: 'Failed', className: 'bg-red-50 text-red-700' },
};

export default function MeetingStatus({ status }: { status: Status }) {
  const style = styles[status] ?? styles.uploaded;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${style.className}`}
    >
      {status === 'processing' ? (
        <LoadingSpinner className="size-3" />
      ) : (
        <span className="size-1.5 rounded-full bg-current" aria-hidden="true" />
      )}
      {style.label}
    </span>
  );
}
