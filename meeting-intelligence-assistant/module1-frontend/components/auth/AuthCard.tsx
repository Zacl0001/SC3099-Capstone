import Link from 'next/link';
import type { ReactNode } from 'react';
import { LogoIcon } from '@/components/common/Icons';
import { MOCK_AUTH } from '@/lib/config';

interface AuthCardProps {
  title: string;
  subtitle: string;
  children: ReactNode;
  footer: ReactNode;
}

/** Centered card layout shared by the login and register pages. */
export default function AuthCard({ title, subtitle, children, footer }: AuthCardProps) {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-4 py-12">
      <Link href="/" className="mb-8 flex items-center gap-2 text-lg font-semibold text-slate-900">
        <LogoIcon className="size-7 text-brand-600" />
        Meeting Intelligence
      </Link>
      <div className="w-full max-w-sm rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
        <h1 className="text-xl font-semibold text-slate-900">{title}</h1>
        <p className="mt-1 text-sm text-slate-500">{subtitle}</p>
        <div className="mt-6">{children}</div>
      </div>
      <p className="mt-6 text-sm text-slate-600">{footer}</p>
      {MOCK_AUTH && (
        <p className="mt-4 max-w-sm text-center text-xs text-amber-700">
          Demo mode: accounts are stored in this browser only.
        </p>
      )}
    </main>
  );
}
