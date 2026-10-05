'use client';

// Login page. Calls POST /api/auth/login, then redirects to ?next= or /dashboard.

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useEffect } from 'react';
import AuthCard from '@/components/auth/AuthCard';
import { useAuth } from '@/components/auth/AuthProvider';
import LoginForm, { safeNext } from '@/components/auth/LoginForm';
import { PageLoader } from '@/components/common/LoadingSpinner';

function RedirectIfSignedIn() {
  const { status } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  useEffect(() => {
    if (status === 'authenticated') router.replace(safeNext(searchParams.get('next')));
  }, [status, router, searchParams]);
  return null;
}

export default function LoginPage() {
  const { status } = useAuth();
  if (status === 'loading') return <PageLoader />;

  return (
    <AuthCard
      title="Welcome back"
      subtitle="Sign in to see your meetings."
      footer={
        <>
          Don&apos;t have an account?{' '}
          <Link href="/register" className="font-medium text-brand-600 hover:text-brand-700">
            Create one
          </Link>
        </>
      }
    >
      <Suspense>
        <RedirectIfSignedIn />
        <LoginForm />
      </Suspense>
    </AuthCard>
  );
}
