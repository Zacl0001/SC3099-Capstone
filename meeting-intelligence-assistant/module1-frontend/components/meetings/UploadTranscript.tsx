'use client';

import { useRouter } from 'next/navigation';
import { useRef, useState, type DragEvent, type FormEvent } from 'react';
import { inputClass } from '@/components/auth/FormField';
import Button from '@/components/common/Button';
import ErrorMessage from '@/components/common/ErrorMessage';
import { FileIcon, UploadIcon, XIcon } from '@/components/common/Icons';
import * as api from '@/lib/api';
import { MAX_TRANSCRIPT_BYTES, TRANSCRIPT_EXTENSIONS } from '@/lib/config';
import { errorMessage } from '@/lib/errors';
import { formatBytes } from '@/lib/format';
import { SAMPLE_TRANSCRIPT, SAMPLE_TRANSCRIPT_TITLE } from '@/lib/sampleTranscript';

type Source = 'file' | 'paste';
type Step = 'idle' | 'creating' | 'uploading' | 'processing';

const stepLabel: Record<Step, string> = {
  idle: '',
  creating: 'Creating meeting…',
  uploading: 'Uploading transcript…',
  processing: 'Starting analysis…',
};

function validateFile(file: File): string | null {
  const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
  if (!TRANSCRIPT_EXTENSIONS.includes(ext)) {
    return `Unsupported file type. Please upload one of: ${TRANSCRIPT_EXTENSIONS.join(', ')}`;
  }
  if (file.size === 0) return 'This file is empty.';
  if (file.size > MAX_TRANSCRIPT_BYTES) return `File is too large (max ${formatBytes(MAX_TRANSCRIPT_BYTES)}).`;
  return null;
}

function titleFromFileName(name: string): string {
  return name
    .replace(/\.[^.]+$/, '')
    .replace(/[_-]+/g, ' ')
    .trim();
}

export default function UploadTranscript() {
  const router = useRouter();
  const fileInput = useRef<HTMLInputElement>(null);

  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [source, setSource] = useState<Source>('file');
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState('');
  const [autoProcess, setAutoProcess] = useState(true);
  const [dragging, setDragging] = useState(false);

  const [step, setStep] = useState<Step>('idle');
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const busy = step !== 'idle';

  function selectFile(f: File | undefined) {
    if (!f) return;
    const problem = validateFile(f);
    if (problem) {
      setError(problem);
      setFile(null);
      return;
    }
    setError(null);
    setFile(f);
    if (!title.trim()) setTitle(titleFromFileName(f.name));
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDragging(false);
    if (!busy) selectFile(e.dataTransfer.files[0]);
  }

  function loadSample() {
    setSource('paste');
    setText(SAMPLE_TRANSCRIPT);
    if (!title.trim()) setTitle(SAMPLE_TRANSCRIPT_TITLE);
    setError(null);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    if (!title.trim()) return setError('Please give the meeting a title.');
    let upload: File;
    if (source === 'file') {
      if (!file) return setError('Please choose a transcript file.');
      upload = file;
    } else {
      if (!text.trim()) return setError('Please paste the transcript text.');
      upload = new File([text], 'transcript.txt', { type: 'text/plain' });
      if (upload.size > MAX_TRANSCRIPT_BYTES) return setError('Transcript is too long.');
    }

    let meetingId: number | string | null = null;
    try {
      setStep('creating');
      const meeting = await api.createMeeting({
        title: title.trim(),
        description: description.trim() || undefined,
      });
      meetingId = meeting.id;

      setStep('uploading');
      setProgress(0);
      await api.uploadTranscript(meeting.id, upload, setProgress);
    } catch (err) {
      // Don't leave an empty meeting behind if the upload itself failed.
      if (meetingId !== null) api.deleteMeeting(meetingId).catch(() => {});
      setError(errorMessage(err, 'Upload failed. Please try again.'));
      setStep('idle');
      return;
    }

    if (autoProcess) {
      setStep('processing');
      // If this fails the meeting page offers a "Start analysis" button.
      await api.processMeeting(meetingId).catch(() => {});
    }
    router.push(`/meetings/${meetingId}`);
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor="meeting-title" className="mb-1.5 block text-sm font-medium text-slate-700">
            Meeting title
          </label>
          <input
            id="meeting-title"
            className={inputClass}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Weekly standup – 5 Oct"
            maxLength={200}
            disabled={busy}
            required
          />
        </div>
        <div>
          <label htmlFor="meeting-description" className="mb-1.5 block text-sm font-medium text-slate-700">
            Description <span className="font-normal text-slate-400">(optional)</span>
          </label>
          <input
            id="meeting-description"
            className={inputClass}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Project, attendees, context…"
            maxLength={500}
            disabled={busy}
          />
        </div>
      </div>

      <div>
        <div className="mb-2 flex items-center justify-between gap-2">
          <div role="tablist" aria-label="Transcript source" className="inline-flex rounded-lg bg-slate-100 p-0.5">
            {(['file', 'paste'] as const).map((s) => (
              <button
                key={s}
                type="button"
                role="tab"
                aria-selected={source === s}
                onClick={() => setSource(s)}
                disabled={busy}
                className={`rounded-md px-3 py-1 text-sm font-medium ${
                  source === s ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                {s === 'file' ? 'Upload file' : 'Paste text'}
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={loadSample}
            disabled={busy}
            className="text-sm font-medium text-brand-600 hover:text-brand-700"
          >
            Use sample transcript
          </button>
        </div>

        {source === 'file' ? (
          file ? (
            <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
              <FileIcon className="size-6 text-brand-600" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-slate-900">{file.name}</p>
                <p className="text-xs text-slate-500">{formatBytes(file.size)}</p>
              </div>
              {!busy && (
                <button
                  type="button"
                  onClick={() => setFile(null)}
                  className="rounded-md p-1 text-slate-500 hover:bg-slate-200 hover:text-slate-900"
                  aria-label="Remove file"
                >
                  <XIcon className="size-4" />
                </button>
              )}
            </div>
          ) : (
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={onDrop}
              className={`flex flex-col items-center rounded-xl border-2 border-dashed px-6 py-10 text-center transition ${
                dragging ? 'border-brand-500 bg-brand-50' : 'border-slate-300 bg-white'
              }`}
            >
              <UploadIcon className="size-8 text-slate-400" />
              <p className="mt-3 text-sm text-slate-700">
                Drag and drop your transcript here, or{' '}
                <button
                  type="button"
                  onClick={() => fileInput.current?.click()}
                  className="font-medium text-brand-600 hover:text-brand-700"
                >
                  browse
                </button>
              </p>
              <p className="mt-1 text-xs text-slate-500">
                {TRANSCRIPT_EXTENSIONS.join(', ')} · up to {formatBytes(MAX_TRANSCRIPT_BYTES)}
              </p>
              <input
                ref={fileInput}
                type="file"
                accept={TRANSCRIPT_EXTENSIONS.join(',')}
                className="sr-only"
                tabIndex={-1}
                onChange={(e) => {
                  selectFile(e.target.files?.[0]);
                  e.target.value = '';
                }}
              />
            </div>
          )
        ) : (
          <textarea
            aria-label="Transcript text"
            className={`${inputClass} min-h-56 font-mono text-xs leading-relaxed`}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={'[00:00:05] Alice: Morning everyone…\n[00:00:21] Bob: …'}
            disabled={busy}
          />
        )}
      </div>

      <label className="flex items-center gap-2 text-sm text-slate-700">
        <input
          type="checkbox"
          checked={autoProcess}
          onChange={(e) => setAutoProcess(e.target.checked)}
          disabled={busy}
          className="size-4 rounded border-slate-300 accent-brand-600"
        />
        Analyse automatically after upload (summary, action items, decisions)
      </label>

      <ErrorMessage message={error} />

      {busy && (
        <div aria-live="polite">
          <div className="mb-1 flex justify-between text-xs text-slate-600">
            <span>{stepLabel[step]}</span>
            {step === 'uploading' && <span>{progress}%</span>}
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-slate-100">
            <div
              className="h-full rounded-full bg-brand-600 transition-all"
              style={{ width: step === 'creating' ? '10%' : step === 'uploading' ? `${10 + progress * 0.8}%` : '100%' }}
            />
          </div>
        </div>
      )}

      <div className="flex justify-end">
        <Button type="submit" loading={busy}>
          <UploadIcon className="size-4" />
          Upload transcript
        </Button>
      </div>
    </form>
  );
}
