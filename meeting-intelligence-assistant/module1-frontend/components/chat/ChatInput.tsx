'use client';

import { useState, type FormEvent, type KeyboardEvent } from 'react';
import { SendIcon } from '@/components/common/Icons';

interface ChatInputProps {
  onSend: (question: string) => void;
  disabled?: boolean;
}

const MAX_LENGTH = 1000;

export default function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [value, setValue] = useState('');

  function submit(e?: FormEvent) {
    e?.preventDefault();
    const question = value.trim();
    if (!question || disabled) return;
    onSend(question);
    setValue('');
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
        rows={1}
        maxLength={MAX_LENGTH}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={onKeyDown}
        placeholder="Ask a question about this meeting…"
        className="field-sizing-content max-h-40 min-h-10 flex-1 resize-none rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 focus:outline-none"
      />
      <button
        type="submit"
        disabled={disabled || !value.trim()}
        className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-brand-600 text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
        aria-label="Send"
      >
        <SendIcon className="size-4" />
      </button>
    </form>
  );
}
