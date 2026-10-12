'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect, type ReactNode } from 'react';
import Button from '@/components/common/Button';
import { AlertIcon } from '@/components/common/Icons';
import { PageLoader } from '@/components/common/LoadingSpinner';
import { useAuth } from './AuthProvider';

/** Redirects to /login (remembering where the user was going) when signed out. */
export default function ProtectedRoute({ children }: { children: ReactNode }) {
  const { status, error, retry } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (status === 'unauthenticated') {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    }
  }, [status, router, pathname]);

  // Backend unreachable: keep the stored session and let the user retry
  // instead of bouncing them to a login form that would fail the same way.
  if (status === 'unavailable') {
    return (
      <main className="flex min-h-screen items-center justify-center px-4">
        <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
          <AlertIcon className="mx-auto size-10 text-red-500" />
          <h1 className="mt-4 text-lg font-semibold text-slate-900">Can&apos;t reach the server</h1>
          <p className="mt-2 text-sm text-slate-600">{error}</p>
          <div className="mt-6 flex justify-center gap-3">
            <Button onClick={retry}>Try again</Button>
            <Link
              href={`/login?next=${encodeURIComponent(pathname)}`}
              className="inline-flex h-10 items-center px-3 text-sm font-medium text-slate-600 hover:text-slate-900"
            >
              Go to sign in
            </Link>
          </div>
        </div>
      </main>
    );
  }

  if (status !== 'authenticated') return <PageLoader />;
  return <>{children}</>;
}
