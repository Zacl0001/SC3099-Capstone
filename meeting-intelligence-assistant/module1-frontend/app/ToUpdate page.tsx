'use client';

// Landing page. Signed-in users get a shortcut to their dashboard.

import Link from 'next/link';
import { useAuth } from '@/components/auth/AuthProvider';
import { ButtonLink } from '@/components/common/Button';
import { ChatIcon, CheckCircleIcon, GavelIcon, ListIcon, LogoIcon, SparklesIcon } from '@/components/common/Icons';

const features = [
  { icon: SparklesIcon, title: 'Summaries', text: 'An executive summary, key points and topics for every meeting.' },
  { icon: ListIcon, title: 'Action items', text: 'Who owes what, and by when – extracted automatically.' },
  { icon: GavelIcon, title: 'Decisions', text: 'Every decision captured with the moment it was made.' },
  { icon: ChatIcon, title: 'Ask questions', text: 'Chat with your meeting and get answers linked to the transcript.' },
];

export default function Home() {
  const { status } = useAuth();
  const signedIn = status === 'authenticated';

  return (
    <div className="min-h-screen bg-gradient-to-b from-brand-50 to-slate-50">
      <header className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <span className="flex items-center gap-2 font-semibold text-slate-900">
          <LogoIcon className="size-6 text-brand-600" />
          Meeting Intelligence
        </span>
        {status !== 'loading' &&
          (signedIn ? (
            <ButtonLink href="/dashboard" size="sm">
              Go to dashboard
            </ButtonLink>
          ) : (
            <div className="flex items-center gap-2">
              <Link href="/login" className="px-3 text-sm font-medium text-slate-700 hover:text-slate-900">
                Sign in
              </Link>
              <ButtonLink href="/register" size="sm">
                Get started
              </ButtonLink>
            </div>
          ))}
      </header>

      <main className="mx-auto max-w-6xl px-4 pt-16 pb-24 sm:px-6">
        <div className="mx-auto max-w-2xl text-center">
          <h1 className="text-4xl font-bold tracking-tight text-slate-900 sm:text-5xl">
            Understand any meeting in minutes
          </h1>
          <p className="mt-5 text-lg text-slate-600">
            Upload a meeting transcript and get a summary, action items and key decisions – then ask follow-up
            questions with answers grounded in what was actually said.
          </p>
          <div className="mt-8 flex justify-center gap-3">
            <ButtonLink href={signedIn ? '/meetings/new' : '/register'}>
              {signedIn ? 'Upload a transcript' : 'Get started'}
            </ButtonLink>
            {!signedIn && (
              <ButtonLink href="/login" variant="secondary">
                Sign in
              </ButtonLink>
            )}
          </div>
        </div>

        <ul className="mt-20 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {features.map(({ icon: Icon, title, text }) => (
            <li key={title} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <Icon className="size-6 text-brand-600" />
              <h2 className="mt-4 font-semibold text-slate-900">{title}</h2>
              <p className="mt-1 text-sm text-slate-600">{text}</p>
            </li>
          ))}
        </ul>

        <p className="mt-12 flex items-center justify-center gap-2 text-sm text-slate-500">
          <CheckCircleIcon className="size-4 text-emerald-600" />
          Every AI answer cites the transcript lines it came from.
        </p>
      </main>
    </div>
  );
}
