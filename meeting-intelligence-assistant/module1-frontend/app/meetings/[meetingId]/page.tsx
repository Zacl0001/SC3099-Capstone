'use client';

// Meeting detail: processing status, then the options available once the
// transcript has been analysed - summary, action items, decisions, Q&A chat
// with citations - plus the transcript itself (where citations point to).

import Link from 'next/link';
import { useParams, usePathname, useRouter, useSearchParams } from 'next/navigation';
import {
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ComponentType,
  type ReactNode,
  type SVGProps,
} from 'react';
import ActionItemList from '@/components/action-items/ActionItemList';
import Button from '@/components/common/Button';
import ChatWindow from '@/components/chat/ChatWindow';
import DecisionList from '@/components/decisions/DecisionList';
import ErrorMessage from '@/components/common/ErrorMessage';
import {
  AlertIcon,
  ArrowLeftIcon,
  ArrowRightIcon,
  CalendarIcon,
  ChatIcon,
  FileIcon,
  GavelIcon,
  ListIcon,
  SparklesIcon,
  TrashIcon,
} from '@/components/common/Icons';
import LoadingSpinner, { PageLoader } from '@/components/common/LoadingSpinner';
import Modal from '@/components/common/Modal';
import MeetingStatus from '@/components/meetings/MeetingStatus';
import TranscriptViewer from '@/components/meetings/TranscriptViewer';
import SummaryView from '@/components/summary/SummaryView';
import * as api from '@/lib/api';
import { errorMessage } from '@/lib/errors';
import { formatDateTime } from '@/lib/format';
import { useAsync } from '@/lib/hooks';
import { findSegmentForCitation, parseTranscript } from '@/lib/transcript';
import type { ChatMessage, Citation, Meeting } from '@/lib/types';

const POLL_MS = 3000;

type Tab = 'overview' | 'action-items' | 'decisions' | 'chat' | 'transcript';
const TABS: { id: Tab; label: string; icon: ComponentType<SVGProps<SVGSVGElement>> }[] = [
  { id: 'overview', label: 'Summary', icon: SparklesIcon },
  { id: 'action-items', label: 'Action items', icon: ListIcon },
  { id: 'decisions', label: 'Decisions', icon: GavelIcon },
  { id: 'chat', label: 'Ask AI', icon: ChatIcon },
  { id: 'transcript', label: 'Transcript', icon: FileIcon },
];

function chatKey(id: string) {
  return `mia.chat.${id}`;
}

function loadChat(id: string): ChatMessage[] {
  try {
    return JSON.parse(sessionStorage.getItem(chatKey(id)) ?? '[]') as ChatMessage[];
  } catch {
    return [];
  }
}

export default function MeetingPage() {
  const { meetingId } = useParams<{ meetingId: string }>();
  return (
    <Suspense fallback={<PageLoader />}>
      {/* key: reset all per-meeting state when navigating between meetings */}
      <MeetingDetail key={meetingId} meetingId={meetingId} />
    </Suspense>
  );
}

function MeetingDetail({ meetingId }: { meetingId: string }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  // --- Meeting (polled while processing) ----------------------------------
  const initial = useAsync(() => api.getMeeting(meetingId), `meeting-${meetingId}`);
  const [polled, setPolled] = useState<Meeting | null>(null);
  const meeting = polled ?? initial.data;
  const status = meeting?.status;
  const completed = status === 'completed';

  useEffect(() => {
    if (status !== 'processing') return;
    const timer = setInterval(() => {
      api.getMeeting(meetingId).then(setPolled, () => {});
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [status, meetingId]);

  // Re-applied on tab changes because the route's static metadata resets the title.
  useEffect(() => {
    if (meeting) document.title = `${meeting.title} · Meeting Intelligence`;
  }, [meeting, searchParams]);

  // --- Transcript & AI outputs --------------------------------------------
  const transcript = useAsync(
    () => api.getTranscript(meetingId),
    `transcript-${meetingId}-${meeting?.transcript_file_name ?? ''}-${meeting?.updated_at ?? ''}`,
    !!meeting,
  );
  const segments = useMemo(
    () => (transcript.data ? parseTranscript(transcript.data.raw_text) : []),
    [transcript.data],
  );
  const summary = useAsync(() => api.getSummary(meetingId), `summary-${meetingId}`, completed);
  const actionItems = useAsync(() => api.getActionItems(meetingId), `actions-${meetingId}`, completed);
  const decisions = useAsync(() => api.getDecisions(meetingId), `decisions-${meetingId}`, completed);

  // --- Tabs (kept in the URL so they survive refresh) ---------------------
  const requested = (searchParams.get('tab') as Tab | null) ?? 'overview';
  const tab: Tab = !completed ? 'transcript' : TABS.some((t) => t.id === requested) ? requested : 'overview';
  const setTab = useCallback(
    (next: Tab) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set('tab', next);
      router.replace(`${pathname}?${params}`, { scroll: false });
    },
    [router, pathname, searchParams],
  );

  // --- Chat history (kept for this browser session) -----------------------
  const [messages, setMessages] = useState<ChatMessage[]>(() =>
    typeof window === 'undefined' ? [] : loadChat(meetingId),
  );
  useEffect(() => {
    try {
      sessionStorage.setItem(chatKey(meetingId), JSON.stringify(messages));
    } catch {
      // ignore
    }
  }, [meetingId, messages]);

  // --- Jump from a citation / action item / decision to the transcript ----
  const [highlight, setHighlight] = useState<{ id: string | null; nonce: number }>({ id: null, nonce: 0 });
  const [sourceNotFound, setSourceNotFound] = useState(false);
  const viewSource = useCallback(
    (ref: Citation) => {
      const seg = findSegmentForCitation(segments, ref);
      setHighlight({ id: seg?.id ?? null, nonce: Date.now() });
      setSourceNotFound(!seg);
      setTab('transcript');
    },
    [segments, setTab],
  );
  const viewEvidence = useCallback(
    (item: { id: number | string; evidence?: string | null; timestamp?: string | null }) =>
      viewSource({ chunk_id: '', text: item.evidence ?? '', start_time: item.timestamp }),
    [viewSource],
  );

  // --- Actions -------------------------------------------------------------
  const [actionError, setActionError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  async function startProcessing() {
    setActionError(null);
    setStarting(true);
    try {
      setPolled(await api.processMeeting(meetingId));
    } catch (err) {
      setActionError(errorMessage(err, 'Could not start the analysis.'));
    } finally {
      setStarting(false);
    }
  }

  async function handleDelete() {
    setDeleting(true);
    try {
      await api.deleteMeeting(meetingId);
      try {
        sessionStorage.removeItem(chatKey(meetingId));
      } catch {
        // ignore
      }
      router.push('/meetings');
    } catch (err) {
      setActionError(errorMessage(err, 'Could not delete the meeting.'));
      setConfirmDelete(false);
      setDeleting(false);
    }
  }

  // --- Render ---------------------------------------------------------------
  if (initial.loading && !meeting) return <PageLoader label="Loading meeting…" />;
  if (!meeting) {
    return (
      <div className="space-y-4">
        <BackLink />
        <ErrorMessage message={initial.error ?? 'Meeting not found.'} onRetry={initial.reload} />
      </div>
    );
  }

  const counts: Partial<Record<Tab, number | undefined>> = {
    'action-items': actionItems.data?.length,
    decisions: decisions.data?.length,
  };

  return (
    <div className="space-y-6">
      <div>
        <BackLink />
        <div className="mt-3 flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-2xl font-semibold break-words text-slate-900">{meeting.title}</h1>
              <MeetingStatus status={meeting.status} />
            </div>
            <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-500">
              <span className="inline-flex items-center gap-1.5">
                <CalendarIcon className="size-4" />
                {formatDateTime(meeting.created_at)}
              </span>
              {meeting.transcript_file_name && (
                <span className="inline-flex items-center gap-1.5">
                  <FileIcon className="size-4" />
                  {meeting.transcript_file_name}
                </span>
              )}
            </div>
            {meeting.description && <p className="mt-2 text-sm text-slate-600">{meeting.description}</p>}
          </div>
          <Button variant="secondary" size="sm" onClick={() => setConfirmDelete(true)}>
            <TrashIcon className="size-4" />
            Delete
          </Button>
        </div>
      </div>

      <ErrorMessage message={actionError} />

      <StatusPanel meeting={meeting} starting={starting} onStart={startProcessing} />

      <div className="border-b border-slate-200">
        <nav role="tablist" aria-label="Meeting sections" className="-mb-px flex gap-1 overflow-x-auto">
          {TABS.map(({ id, label, icon: Icon }) => {
            const disabled = !completed && id !== 'transcript';
            const active = tab === id;
            return (
              <button
                key={id}
                type="button"
                role="tab"
                aria-selected={active}
                disabled={disabled}
                title={disabled ? 'Available once the analysis has finished' : undefined}
                onClick={() => setTab(id)}
                className={`flex shrink-0 items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium whitespace-nowrap transition ${
                  active
                    ? 'border-brand-600 text-brand-700'
                    : 'border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-800'
                } disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:border-transparent`}
              >
                <Icon className="size-4" />
                {label}
                {counts[id] !== undefined && (
                  <span className="rounded-full bg-slate-100 px-1.5 text-xs text-slate-600">{counts[id]}</span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      <div role="tabpanel">
        {tab === 'overview' && (
          <div className="grid gap-6 lg:grid-cols-3">
            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm lg:col-span-2">
              <Section state={summary}>{(data) => <SummaryView summary={data} />}</Section>
            </div>
            <div className="space-y-3">
              <h2 className="text-sm font-semibold tracking-wide text-slate-500 uppercase">What next?</h2>
              <OptionCard
                icon={ListIcon}
                title="Action items"
                text={
                  actionItems.data
                    ? `${actionItems.data.length} task${actionItems.data.length === 1 ? '' : 's'} with owners and deadlines`
                    : 'Tasks with owners and deadlines'
                }
                onClick={() => setTab('action-items')}
              />
              <OptionCard
                icon={GavelIcon}
                title="Decisions"
                text={
                  decisions.data
                    ? `${decisions.data.length} decision${decisions.data.length === 1 ? '' : 's'} made in this meeting`
                    : 'Key decisions made in this meeting'
                }
                onClick={() => setTab('decisions')}
              />
              <OptionCard
                icon={ChatIcon}
                title="Ask a question"
                text="Chat with the meeting and get answers with transcript references"
                onClick={() => setTab('chat')}
              />
              <OptionCard
                icon={FileIcon}
                title="Read the transcript"
                text={`${segments.length} lines, searchable`}
                onClick={() => setTab('transcript')}
              />
            </div>
          </div>
        )}

        {tab === 'action-items' && (
          <Section state={actionItems}>
            {(data) => <ActionItemList items={data} onViewSource={viewEvidence} />}
          </Section>
        )}

        {tab === 'decisions' && (
          <Section state={decisions}>
            {(data) => <DecisionList decisions={data} onViewSource={viewEvidence} />}
          </Section>
        )}

        {tab === 'chat' && (
          <ChatWindow
            meetingId={meetingId}
            messages={messages}
            onMessagesChange={setMessages}
            onViewCitation={viewSource}
          />
        )}

        {tab === 'transcript' && (
          <div className="space-y-3">
            {sourceNotFound && (
              <p className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-800">
                Couldn&apos;t pinpoint that passage in the transcript – it may have been paraphrased.
              </p>
            )}
            <Section state={transcript}>
              {(data) => (
                <TranscriptViewer
                  segments={segments}
                  fileName={data.file_name}
                  highlightId={highlight.id}
                  highlightNonce={highlight.nonce}
                />
              )}
            </Section>
          </div>
        )}
      </div>

      <Modal
        open={confirmDelete}
        title="Delete meeting?"
        onClose={() => !deleting && setConfirmDelete(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setConfirmDelete(false)} disabled={deleting}>
              Cancel
            </Button>
            <Button variant="danger" onClick={handleDelete} loading={deleting}>
              Delete
            </Button>
          </>
        }
      >
        <p>
          “{meeting.title}” and its transcript, summary, action items and decisions will be permanently removed.
        </p>
      </Modal>
    </div>
  );
}

function BackLink() {
  return (
    <Link href="/meetings" className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-900">
      <ArrowLeftIcon className="size-4" />
      Meetings
    </Link>
  );
}

interface SectionProps<T> {
  state: { data: T | undefined; error: string | null; loading: boolean; reload: () => void };
  children: (data: T) => ReactNode;
}

/** Loading / error / content wrapper for one async section. */
function Section<T>({ state, children }: SectionProps<T>) {
  if (state.loading) {
    return (
      <div className="flex justify-center py-12 text-brand-600">
        <LoadingSpinner />
      </div>
    );
  }
  if (state.error) return <ErrorMessage message={state.error} onRetry={state.reload} />;
  if (state.data === undefined) return null;
  return <>{children(state.data)}</>;
}

function StatusPanel({ meeting, starting, onStart }: { meeting: Meeting; starting: boolean; onStart: () => void }) {
  if (meeting.status === 'completed') return null;

  if (meeting.status === 'processing') {
    return (
      <div className="flex items-center gap-4 rounded-xl border border-blue-200 bg-blue-50 p-4">
        <LoadingSpinner className="size-6 text-blue-600" />
        <div>
          <p className="font-medium text-blue-900">Analysing transcript…</p>
          <p className="text-sm text-blue-800">
            Generating the summary, action items and decisions. This page updates automatically.
          </p>
        </div>
      </div>
    );
  }

  if (meeting.status === 'failed') {
    return (
      <div className="flex flex-wrap items-center gap-4 rounded-xl border border-red-200 bg-red-50 p-4">
        <AlertIcon className="size-6 shrink-0 text-red-600" />
        <div className="min-w-0 flex-1">
          <p className="font-medium text-red-900">Analysis failed</p>
          <p className="text-sm text-red-800">{meeting.error_message || 'Something went wrong while processing.'}</p>
        </div>
        <Button onClick={onStart} loading={starting}>
          Retry analysis
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-4 rounded-xl border border-brand-200 bg-brand-50 p-4">
      <SparklesIcon className="size-6 shrink-0 text-brand-600" />
      <div className="min-w-0 flex-1">
        <p className="font-medium text-brand-900">Transcript uploaded</p>
        <p className="text-sm text-brand-900/80">
          Run the analysis to get a summary, action items, decisions and the Q&amp;A assistant.
        </p>
      </div>
      <Button onClick={onStart} loading={starting}>
        Analyse meeting
      </Button>
    </div>
  );
}

interface OptionCardProps {
  icon: ComponentType<SVGProps<SVGSVGElement>>;
  title: string;
  text: string;
  onClick: () => void;
}

function OptionCard({ icon: Icon, title, text, onClick }: OptionCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group flex w-full items-center gap-3 rounded-xl border border-slate-200 bg-white p-4 text-left shadow-sm transition hover:border-brand-200 hover:shadow-md"
    >
      <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
        <Icon className="size-5" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="font-medium text-slate-900 group-hover:text-brand-700">{title}</p>
        <p className="text-sm text-slate-500">{text}</p>
      </div>
      <ArrowRightIcon className="size-4 shrink-0 text-slate-400 group-hover:text-brand-600" />
    </button>
  );
}
