interface LoadingSpinnerProps {
  className?: string;
  label?: string;
}

export default function LoadingSpinner({ className = 'size-5', label }: LoadingSpinnerProps) {
  return (
    <span role="status" className="inline-flex items-center gap-2">
      <svg className={`animate-spin ${className}`} viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" className="opacity-25" />
        <path d="M22 12a10 10 0 0 0-10-10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
      </svg>
      {label ? <span className="text-sm text-slate-600">{label}</span> : <span className="sr-only">Loading</span>}
    </span>
  );
}

export function PageLoader({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="flex min-h-[40vh] items-center justify-center text-brand-600">
      <LoadingSpinner className="size-6" label={label} />
    </div>
  );
}
