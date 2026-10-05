'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { errorMessage } from './errors';

interface AsyncState<T> {
  data: T | undefined;
  error: string | null;
  loading: boolean;
  reload: () => void;
}

interface Settled<T> {
  key: string;
  data?: T;
  error: string | null;
}

/**
 * Runs `fn` while `enabled` is true, re-running whenever `key` changes or
 * `reload()` is called. Loading is derived from whether the latest request
 * has settled, and stale responses are ignored.
 */
export function useAsync<T>(fn: () => Promise<T>, key: string, enabled = true): AsyncState<T> {
  const [nonce, setNonce] = useState(0);
  const [settled, setSettled] = useState<Settled<T> | null>(null);
  const fnRef = useRef(fn);
  const requestKey = `${key}#${nonce}`;

  useEffect(() => {
    fnRef.current = fn;
  });

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    fnRef.current().then(
      (data) => !cancelled && setSettled({ key: requestKey, data, error: null }),
      (err) => !cancelled && setSettled({ key: requestKey, error: errorMessage(err) }),
    );
    return () => {
      cancelled = true;
    };
  }, [requestKey, enabled]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);
  const current = settled?.key === requestKey;
  // While reloading the same key, keep showing the previous data.
  const sameResource = settled?.key.startsWith(`${key}#`) ?? false;

  return {
    data: sameResource ? settled?.data : undefined,
    error: current ? settled!.error : null,
    loading: enabled && !current,
    reload,
  };
}
