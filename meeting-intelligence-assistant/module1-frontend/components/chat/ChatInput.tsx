'use client';

import type { FormEvent, KeyboardEvent } from 'react';
import { SendIcon } from '@/components/common/Icons';

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: (question: string) => void;
  disabled?: boolean;
}

const MAX_LENGTH = 1000;

export default function ChatInput({ value, onChange, onSend, disabled }: ChatInputProps) {
  function submit(e?: FormEvent) {
    e?.preventDefault();
    const question = value.trim();
    if (!question || disabled) return;
    onSend(question);
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  }

  return (
    <form onSubmit={submit} className="flex items-end gap-2 border-t border-slate-200 bg-white p-3">
      <textarea
        aria-label="Ask a question about this meeting"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={onKeyDown}
        maxLength={MAX_LENGTH}
        rows={1}
        placeholder="Ask a question about this meeting…"
        disabled={disabled}
        className="max-h-32 min-h-10 flex-1 resize-y rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none placeholder:text-slate-400 focus:border-brand-400 focus:ring-2 focus:ring-brand-100 disabled:bg-slate-50 disabled:text-slate-500"
      />
      <button
        type="submit"
        disabled={disabled || value.trim().length === 0}
        className="inline-flex size-10 shrink-0 items-center justify-center rounded-lg bg-brand-600 text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:bg-slate-300"
        aria-label="Send question"
      >
        <SendIcon className="size-4" />
      </button>
    </form>
  );
}
