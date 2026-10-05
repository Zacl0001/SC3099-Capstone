'use client';

import { useRouter } from 'next/navigation';
import { useState, type FormEvent } from 'react';
import Button from '@/components/common/Button';
import ErrorMessage from '@/components/common/ErrorMessage';
import { errorMessage } from '@/lib/errors';
import { useAuth } from './AuthProvider';
import FormField from './FormField';

const MIN_PASSWORD = 8; // matches RegisterRequest in module2-backend

export default function RegisterForm() {
  const { register } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [touched, setTouched] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const passwordError =
    touched && password.length < MIN_PASSWORD ? `Password must be at least ${MIN_PASSWORD} characters.` : undefined;
  const confirmError = touched && confirm !== password ? 'Passwords do not match.' : undefined;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setTouched(true);
    setError(null);
    if (password.length < MIN_PASSWORD || confirm !== password) return;

    setSubmitting(true);
    try {
      await register(email.trim(), password);
      router.replace('/dashboard');
    } catch (err) {
      setError(errorMessage(err, 'Registration failed. Please try again.'));
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <ErrorMessage message={error} />
      <FormField
        id="email"
        label="Email"
        type="email"
        autoComplete="email"
        required
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="you@example.com"
      />
      <FormField
        id="password"
        label="Password"
        type="password"
        autoComplete="new-password"
        required
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        error={passwordError}
        hint={`At least ${MIN_PASSWORD} characters.`}
      />
      <FormField
        id="confirm-password"
        label="Confirm password"
        type="password"
        autoComplete="new-password"
        required
        value={confirm}
        onChange={(e) => setConfirm(e.target.value)}
        error={confirmError}
      />
      <Button type="submit" loading={submitting} className="w-full">
        Create account
      </Button>
    </form>
  );
}
