import Link from 'next/link';
import { ArrowRightIcon, CalendarIcon, FileIcon } from '@/components/common/Icons';
import { formatDate } from '@/lib/format';
import type { Meeting } from '@/lib/types';
import MeetingStatus from './MeetingStatus';

export default function MeetingCard({ meeting }: { meeting: Meeting }) {
  return (
    <Link
      href={`/meetings/${meeting.id}`}
      className="group flex items-center gap-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition hover:border-brand-200 hover:shadow-md"
    >
      <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
        <FileIcon className="size-5" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="truncate font-medium text-slate-900 group-hover:text-brand-700">{meeting.title}</h3>
          <MeetingStatus status={meeting.status} />
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
          <span className="inline-flex items-center gap-1">
            <CalendarIcon className="size-3.5" />
            {formatDate(meeting.created_at)}
          </span>
          {meeting.transcript_file_name && <span className="truncate">{meeting.transcript_file_name}</span>}
          {meeting.description && <span className="truncate">{meeting.description}</span>}
        </div>
      </div>
      <ArrowRightIcon className="size-4 shrink-0 text-slate-400 transition group-hover:translate-x-0.5 group-hover:text-brand-600" />
    </Link>
  );
}
