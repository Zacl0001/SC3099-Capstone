import type { ReactNode } from 'react';
import ProtectedRoute from '@/components/auth/ProtectedRoute';
import Navbar from './Navbar';

/** Layout for every signed-in page: auth guard + navbar + content width. */
export default function AppShell({ children }: { children: ReactNode }) {
  return (
    <ProtectedRoute>
      <Navbar />
      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">{children}</main>
    </ProtectedRoute>
  );
}
