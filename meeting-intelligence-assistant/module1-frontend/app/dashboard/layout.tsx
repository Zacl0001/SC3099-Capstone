import type { ReactNode } from 'react';
import AppShell from '@/components/common/AppShell';

export const metadata = { title: 'Dashboard' };

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
