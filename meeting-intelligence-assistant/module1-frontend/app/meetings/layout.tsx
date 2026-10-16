import type { ReactNode } from 'react';
import AppShell from '@/components/common/AppShell';

export const metadata = { title: 'Meetings' };

export default function MeetingsLayout({ children }: { children: ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
