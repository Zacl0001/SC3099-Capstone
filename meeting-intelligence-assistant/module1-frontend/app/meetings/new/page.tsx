'use client';

// Upload a new meeting transcript.

import Link from 'next/link';
import { ArrowLeftIcon } from '@/components/common/Icons';
import UploadTranscript from '@/components/meetings/UploadTranscript';

export default function NewMeetingPage() {
  return (
    <div className="mx-auto max-w-3xl">
      <Link
        href="/meetings"
        className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-900"
      >
        <ArrowLeftIcon className="size-4" />
        Meetings
      </Link>
      <h1 className="mt-3 text-2xl font-semibold text-slate-900">Upload a transcript</h1>
      <p className="mt-1 text-sm text-slate-500">
        The transcript is stored in your account. Once it&apos;s analysed you can view the summary, action items and
        decisions, and ask questions about it.
      </p>
      <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
        <UploadTranscript />
      </div>
    </div>
  );
}
