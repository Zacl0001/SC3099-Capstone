// Global application layout: global CSS, page metadata and the auth provider.
// Signed-in pages add the navbar via components/common/AppShell.

import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import { AuthProvider } from '@/components/auth/AuthProvider';
import './globals.css';

export const metadata: Metadata = {
  title: {
    default: 'Meeting Intelligence Assistant',
    template: '%s · Meeting Intelligence',
  },
  description: 'Upload meeting transcripts and get summaries, action items, decisions and answers with sources.',
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
