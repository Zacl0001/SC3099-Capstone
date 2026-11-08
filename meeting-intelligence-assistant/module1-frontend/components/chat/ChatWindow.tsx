'use client';

import { useEffect, useRef } from 'react';
import { ChatIcon } from '@/components/common/Icons';
import LoadingSpinner from '@/components/common/LoadingSpinner';
import { MOCK_AI } from '@/lib/config';
import type { ChatMessage as ChatMessageType, Citation } from '@/lib/types';
import ChatInput from './ChatInput';
import ChatMessage from './ChatMessage';

const SUGGESTIONS = [
  'What decisions were made?',
  'Who is responsible for what?',
  'Were any risks or blockers raised?',
  'What are the deadlines?',
];

interface ChatWindowProps {
  messages: ChatMessageType[];
  pending: boolean;
  draft: string;
  onDraftChange: (value: string) => void;
  onSend: (question: string) => void;
  onViewCitation?: (citation: Citation) => void;
}

export default function ChatWindow({
  messages,
  pending,
  draft,
  onDraftChange,
  onSend,
  onViewCitation,
}: ChatWindowProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, [messages.length, pending]);

  return (
    <div className="flex h-[min(70vh,680px)] flex-col overflow-hidden rounded-xl border border-slate-200 bg-slate-50 shadow-sm">
      <div className="flex-1 space-y-5 overflow-y-auto p-4" aria-live="polite">
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <ChatIcon className="size-10 text-brand-300" />
            <h3 className="mt-3 font-semibold text-slate-900">Ask anything about this meeting</h3>
            <p className="mt-1 max-w-sm text-sm text-slate-500">
              Answers are grounded in the transcript and include references you can click to see the source.
            </p>
            <div className="mt-5 flex max-w-lg flex-wrap justify-center gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => onSend(s)}
                  disabled={pending}
                  className="rounded-full border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-700 hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {s}
                </button>
              ))}
            </div>
            {MOCK_AI && (
              <p className="mt-6 text-xs text-amber-700">Demo mode: answers come from keyword matching, not an LLM.</p>
            )}
          </div>
        ) : (
          messages.map((m) => <ChatMessage key={m.id} message={m} onViewCitation={onViewCitation} />)
        )}
        {pending && (
          <div className="flex items-center gap-3 text-brand-600">
            <LoadingSpinner className="size-4" label="Searching the transcript…" />
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      <ChatInput value={draft} onChange={onDraftChange} onSend={onSend} disabled={pending} />
    </div>
  );
}
