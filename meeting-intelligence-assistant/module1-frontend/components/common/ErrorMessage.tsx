import { AlertIcon } from './Icons';

interface ErrorMessageProps {
  message: string | null | undefined;
  onRetry?: () => void;
  className?: string;
}

export default function ErrorMessage({ message, onRetry, className = '' }: ErrorMessageProps) {
  if (!message) return null;
  return (
    <div
      role="alert"
      className={`flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 ${className}`}
    >
      <AlertIcon className="mt-0.5 size-4 shrink-0" />
      <p className="flex-1">{message}</p>
      {onRetry && (
        <button type="button" onClick={onRetry} className="font-medium underline underline-offset-2 hover:text-red-900">
          Try again
        </button>
      )}
    </div>
  );
}
