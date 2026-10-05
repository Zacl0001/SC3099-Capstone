'use client';

// All meetings for the signed-in user, with search, status filter and sort.

import { useMemo, useState } from 'react';
import { inputClass } from '@/components/auth/FormField';
import { ButtonLink } from '@/components/common/Button';
import EmptyState from '@/components/common/EmptyState';
import ErrorMessage from '@/components/common/ErrorMessage';
import { FileIcon, SearchIcon, UploadIcon } from '@/components/common/Icons';
import { PageLoader } from '@/components/common/LoadingSpinner';
import MeetingList from '@/components/meetings/MeetingList';
import * as api from '@/lib/api';
import { useAsync } from '@/lib/hooks';
import type { MeetingStatus } from '@/lib/types';

type Sort = 'newest' | 'oldest' | 'title';

export default function MeetingsPage() {
  const { data: meetings, error, loading, reload } = useAsync(api.getMeetings, 'meetings');
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState<MeetingStatus | 'all'>('all');
  const [sort, setSort] = useState<Sort>('newest');

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (meetings ?? [])
      .filter((m) => status === 'all' || m.status === status)
      .filter(
        (m) =>
          !q ||
          m.title.toLowerCase().includes(q) ||
          m.description?.toLowerCase().includes(q) ||
          m.transcript_file_name?.toLowerCase().includes(q),
      )
      .sort((a, b) => {
        if (sort === 'title') return a.title.localeCompare(b.title);
        const cmp = a.created_at.localeCompare(b.created_at);
        return sort === 'newest' ? -cmp : cmp;
      });
  }, [meetings, query, status, sort]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Meetings</h1>
          <p className="mt-1 text-sm text-slate-500">All transcripts stored in your account.</p>
        </div>
        <ButtonLink href="/meetings/new">
          <UploadIcon className="size-4" />
          Upload transcript
        </ButtonLink>
      </div>

      {loading ? (
        <PageLoader />
      ) : error ? (
        <ErrorMessage message={error} onRetry={reload} />
      ) : !meetings || meetings.length === 0 ? (
        <EmptyState
          icon={<FileIcon />}
          title="No meetings yet"
          description="Upload a transcript to get a summary, action items, decisions and a Q&A assistant."
          action={<ButtonLink href="/meetings/new">Upload your first transcript</ButtonLink>}
        />
      ) : (
        <>
          <div className="flex flex-col gap-3 sm:flex-row">
            <div className="relative flex-1">
              <SearchIcon className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-slate-400" />
              <input
                type="search"
                aria-label="Search meetings"
                placeholder="Search by title, description or file name"
                className={`${inputClass} pl-9`}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
            <select
              aria-label="Filter by status"
              className={`${inputClass} sm:w-40`}
              value={status}
              onChange={(e) => setStatus(e.target.value as MeetingStatus | 'all')}
            >
              <option value="all">All statuses</option>
              <option value="completed">Completed</option>
              <option value="processing">Processing</option>
              <option value="uploaded">Uploaded</option>
              <option value="failed">Failed</option>
            </select>
            <select
              aria-label="Sort meetings"
              className={`${inputClass} sm:w-40`}
              value={sort}
              onChange={(e) => setSort(e.target.value as Sort)}
            >
              <option value="newest">Newest first</option>
              <option value="oldest">Oldest first</option>
              <option value="title">Title A–Z</option>
            </select>
          </div>

          {visible.length === 0 ? (
            <p className="py-10 text-center text-sm text-slate-500">No meetings match your filters.</p>
          ) : (
            <MeetingList meetings={visible} />
          )}
        </>
      )}
    </div>
  );
}
