import type { ReactNode } from 'react';
import { AlertIcon, SparklesIcon } from '@/components/common/Icons';
import type { ChatMessage as ChatMessageType, Citation } from '@/lib/types';
import CitationList from './CitationList';

interface ChatMessageProps {
  message: ChatMessageType;
  onViewCitation?: (citation: Citation) => void;
}

/** Turns "[1]" markers in an answer into buttons that open that citation. */
function renderWithMarkers(
  text: string,
  citations: Citation[],
  onViewCitation?: (citation: Citation) => void,
): ReactNode[] {
  return text.split(/(\[\d+\])/g).map((part, i) => {
    const match = part.match(/^\[(\d+)\]$/);
    const citation = match ? citations[Number(match[1]) - 1] : undefined;
    if (!citation) return part;
    return (
      <button
        key={i}
        type="button"
        onClick={() => onViewCitation?.(citation)}
        className="mx-0.5 inline-flex -translate-y-0.5 items-center rounded bg-brand-100 px-1 text-[0.7rem] font-semibold text-brand-700 hover:bg-brand-200"
        title={citation.text}
      >
        {match![1]}
      </button>
    );
  });
}

export default function ChatMessage({ message, onViewCitation }: ChatMessageProps) {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <p className="max-w-[85%] rounded-2xl rounded-br-sm bg-brand-600 px-4 py-2.5 text-sm whitespace-pre-wrap text-white">
          {message.content}
        </p>
      </div>
    );
  }

  const citations = message.citations ?? [];
  return (
    <div className="flex gap-3">
      <div
        className={`flex size-8 shrink-0 items-center justify-center rounded-full ${
          message.error ? 'bg-red-50 text-red-600' : 'bg-brand-50 text-brand-600'
        }`}
      >
        {message.error ? <AlertIcon className="size-4" /> : <SparklesIcon className="size-4" />}
      </div>
      <div className="min-w-0 max-w-[85%] flex-1">
        <div
          className={`rounded-2xl rounded-tl-sm border px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap ${
            message.error ? 'border-red-200 bg-red-50 text-red-800' : 'border-slate-200 bg-white text-slate-800'
          }`}
        >
          {renderWithMarkers(message.content, citations, onViewCitation)}
        </div>
        <CitationList citations={citations} onView={onViewCitation} />
      </div>
    </div>
  );
}
