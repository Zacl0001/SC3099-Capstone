'use client';

// Main user dashboard: welcome, quick stats, upload a new transcript, recent meetings.

import Link from 'next/link';
import { useAuth } from '@/components/auth/AuthProvider';
import EmptyState from '@/components/common/EmptyState';
import ErrorMessage from '@/components/common/ErrorMessage';
import { FileIcon } from '@/components/common/Icons';
import LoadingSpinner from '@/components/common/LoadingSpinner';
import MeetingList from '@/components/meetings/MeetingList';
import UploadTranscript from '@/components/meetings/UploadTranscript';
import * as api from '@/lib/api';
import { useAsync } from '@/lib/hooks';

const RECENT_COUNT = 5;

export default function DashboardPage() {
  const { user } = useAuth();
  const { data: meetings, error, loading, reload } = useAsync(api.getMeetings, 'meetings');

  const name = user?.email.split('@')[0];
  const completed = meetings?.filter((m) => m.status === 'completed').length ?? 0;
  const processing = meetings?.filter((m) => m.status === 'processing').length ?? 0;
  const recent = [...(meetings ?? [])].sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, RECENT_COUNT);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Welcome{name ? `, ${name}` : ''}</h1>
        <p className="mt-1 text-sm text-slate-500">Upload a transcript or pick up where you left off.</p>
      </div>

      <dl className="grid grid-cols-3 gap-3 sm:max-w-xl">
        {[
          { label: 'Meetings', value: meetings?.length },
          { label: 'Analysed', value: completed },
          { label: 'Processing', value: processing },
        ].map((stat) => (
          <div key={stat.label} className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
            <dt className="text-xs font-medium text-slate-500">{stat.label}</dt>
            <dd className="mt-1 text-2xl font-semibold text-slate-900">{loading ? '–' : (stat.value ?? 0)}</dd>
          </div>
        ))}
      </dl>

      <div className="grid gap-8 lg:grid-cols-5">
        <section className="lg:col-span-3">
          <h2 className="mb-3 font-semibold text-slate-900">Upload a new meeting</h2>
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
            <UploadTranscript />
          </div>
        </section>

        <section className="lg:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-semibold text-slate-900">Recent meetings</h2>
            {meetings && meetings.length > 0 && (
              <Link href="/meetings" className="text-sm font-medium text-brand-600 hover:text-brand-700">
                View all
              </Link>
            )}
          </div>
          {loading ? (
            <div className="flex justify-center py-10 text-brand-600">
              <LoadingSpinner />
            </div>
          ) : error ? (
            <ErrorMessage message={error} onRetry={reload} />
          ) : recent.length === 0 ? (
            <EmptyState
              icon={<FileIcon />}
              title="No meetings yet"
              description="Upload your first transcript to see its summary, action items and decisions."
            />
          ) : (
            <MeetingList meetings={recent} />
          )}
        </section>
      </div>
    </div>
  );
}
