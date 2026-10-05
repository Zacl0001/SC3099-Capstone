'use client';

// Registration page. Calls POST /api/auth/register, then logs the user in.

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';
import AuthCard from '@/components/auth/AuthCard';
import { useAuth } from '@/components/auth/AuthProvider';
import RegisterForm from '@/components/auth/RegisterForm';
import { PageLoader } from '@/components/common/LoadingSpinner';

export default function RegisterPage() {
  const { status } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (status === 'authenticated') router.replace('/dashboard');
  }, [status, router]);

  if (status === 'loading') return <PageLoader />;

  return (
    <AuthCard
      title="Create your account"
      subtitle="Upload meeting transcripts and let AI do the note-taking."
      footer={
        <>
          Already have an account?{' '}
          <Link href="/login" className="font-medium text-brand-600 hover:text-brand-700">
            Sign in
          </Link>
        </>
      }
    >
      <RegisterForm />
    </AuthCard>
  );
}
