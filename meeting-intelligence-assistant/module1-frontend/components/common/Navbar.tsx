'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/components/auth/AuthProvider';
import { MOCK_AUTH, MOCK_MEETINGS } from '@/lib/config';
import { LogoIcon, LogoutIcon } from './Icons';

const links = [
  { href: '/dashboard', label: 'Dashboard' },
  { href: '/meetings', label: 'Meetings' },
];

export default function Navbar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  return (
    <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/90 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-4 px-4 sm:px-6">
        <Link href="/dashboard" className="flex items-center gap-2 font-semibold text-slate-900">
          <LogoIcon className="size-6 text-brand-600" />
          <span className="hidden sm:inline">Meeting Intelligence</span>
        </Link>

        <nav className="flex items-center gap-1">
          {links.map((link) => {
            const active = pathname === link.href || pathname.startsWith(`${link.href}/`);
            return (
              <Link
                key={link.href}
                href={link.href}
                aria-current={active ? 'page' : undefined}
                className={`rounded-md px-3 py-1.5 text-sm font-medium ${
                  active ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                }`}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>

        <div className="ml-auto flex items-center gap-3">
          {(MOCK_AUTH || MOCK_MEETINGS) && (
            <span
              className="hidden rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-800 md:inline"
              title="Some API calls are simulated in the browser (see .env.example)"
            >
              Demo mode
            </span>
          )}
          <span className="hidden max-w-48 truncate text-sm text-slate-600 sm:inline" title={user?.email}>
            {user?.email}
          </span>
          <button
            type="button"
            onClick={logout}
            className="flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm text-slate-600 hover:bg-slate-100 hover:text-slate-900"
          >
            <LogoutIcon className="size-4" />
            <span>Log out</span>
          </button>
        </div>
      </div>
    </header>
  );
}
