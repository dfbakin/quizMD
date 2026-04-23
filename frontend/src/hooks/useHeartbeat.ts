import { useCallback, useEffect, useRef } from 'react';
import { studentApi } from '../api/endpoints';
import type { AnswerSave, HeartbeatResponse } from '../types/quiz';

export interface HeartbeatAnchor {
  serverNow: string;
  deadlineAt: string;
}

export interface UseHeartbeatOptions {
  attemptId: number | null;
  sessionToken: string | null;
  /** Always returns the freshest answers — read through a ref so timer scheduling never depends on render identity. */
  getAnswers: () => AnswerSave[];
  onAnchor: (anchor: HeartbeatAnchor) => void;
  /** Called when the server reports the attempt is no longer ours (404 / 409). */
  onInvalidated?: () => void;
  /** Called when server reports `expired:true` or `status:'expired'`. */
  onExpired?: (resp: HeartbeatResponse) => void;
  /** Heartbeat cadence. Default 30s. */
  intervalMs?: number;
  /** Max retry attempts on transient failure. Default 3. */
  maxRetries?: number;
  /** Test seam: replace the network call. */
  send?: (
    attemptId: number,
    sessionToken: string,
    answers: AnswerSave[],
  ) => Promise<HeartbeatResponse>;
}

interface ErrShape {
  response?: { status?: number };
}

function getStatusCode(err: unknown): number | undefined {
  if (typeof err === 'object' && err !== null && 'response' in err) {
    return (err as ErrShape).response?.status;
  }
  return undefined;
}

/**
 * Combined heartbeat + auto-save.
 *
 * Round-trip every `intervalMs` (default 30s), plus immediately on
 * `visibilitychange` (when tab becomes visible) and `online` events. Each
 * round-trip:
 *  1. POSTs ALL current answers (cleared answers must persist as cleared).
 *  2. Receives a fresh (server_now, deadline_at) anchor → forwards to parent.
 *  3. Maintains a rolling localStorage snapshot of the latest answers, so
 *     we can recover after browser crash / network outage even if the very
 *     last submit fails.
 *
 * Retries with exponential back-off on transient failures (max 3 in-flight).
 * 404/409 → onInvalidated (attempt was reset or already submitted server-side).
 */
export function useHeartbeat({
  attemptId,
  sessionToken,
  getAnswers,
  onAnchor,
  onInvalidated,
  onExpired,
  intervalMs = 30_000,
  maxRetries = 3,
  send,
}: UseHeartbeatOptions): { heartbeatNow: () => void } {
  const getAnswersRef = useRef(getAnswers);
  useEffect(() => {
    getAnswersRef.current = getAnswers;
  }, [getAnswers]);

  const onAnchorRef = useRef(onAnchor);
  useEffect(() => {
    onAnchorRef.current = onAnchor;
  }, [onAnchor]);

  const onInvalidatedRef = useRef(onInvalidated);
  useEffect(() => {
    onInvalidatedRef.current = onInvalidated;
  }, [onInvalidated]);

  const onExpiredRef = useRef(onExpired);
  useEffect(() => {
    onExpiredRef.current = onExpired;
  }, [onExpired]);

  const sendRef = useRef(send);
  useEffect(() => {
    sendRef.current = send;
  }, [send]);

  const inFlightRef = useRef(false);
  const stoppedRef = useRef(false);
  const triggerRef = useRef<() => void>(() => {});

  const persistSnapshot = useCallback((id: number, answers: AnswerSave[]) => {
    try {
      localStorage.setItem(`backup_${id}`, JSON.stringify(answers));
    } catch {
      /* quota / disabled — best-effort only */
    }
  }, []);

  useEffect(() => {
    if (!attemptId || !sessionToken) return;
    stoppedRef.current = false;

    const doSend = async (attempt = 0): Promise<void> => {
      if (stoppedRef.current) return;
      if (inFlightRef.current && attempt === 0) return;
      inFlightRef.current = true;
      const answers = getAnswersRef.current();
      persistSnapshot(attemptId, answers);
      try {
        const sender =
          sendRef.current ??
          (async (id, tok, ans) => (await studentApi.heartbeat(id, tok, ans)).data);
        const resp = await sender(attemptId, sessionToken, answers);
        inFlightRef.current = false;
        if (stoppedRef.current) return;

        onAnchorRef.current({
          serverNow: resp.server_now,
          deadlineAt: resp.deadline_at,
        });

        if (resp.status === 'submitted') {
          try {
            localStorage.removeItem(`backup_${attemptId}`);
          } catch {
            /* ignore */
          }
          onInvalidatedRef.current?.();
          return;
        }

        if (resp.expired || resp.status === 'expired') {
          onExpiredRef.current?.(resp);
          return;
        }
      } catch (err: unknown) {
        inFlightRef.current = false;
        if (stoppedRef.current) return;
        const status = getStatusCode(err);
        if (status === 404 || status === 409) {
          onInvalidatedRef.current?.();
          return;
        }
        if (attempt + 1 < maxRetries) {
          const backoffMs = Math.min(15_000, 500 * 2 ** attempt);
          setTimeout(() => {
            void doSend(attempt + 1);
          }, backoffMs);
          return;
        }
        // Out of retries — snapshot is already persisted, will retry next tick.
      }
    };

    triggerRef.current = () => {
      void doSend(0);
    };

    const intervalId = window.setInterval(() => {
      void doSend(0);
    }, intervalMs);

    const onVisibility = () => {
      if (document.visibilityState === 'visible') {
        void doSend(0);
      }
    };
    const onOnline = () => {
      void doSend(0);
    };
    document.addEventListener('visibilitychange', onVisibility);
    window.addEventListener('online', onOnline);
    window.addEventListener('focus', onOnline);

    return () => {
      stoppedRef.current = true;
      window.clearInterval(intervalId);
      document.removeEventListener('visibilitychange', onVisibility);
      window.removeEventListener('online', onOnline);
      window.removeEventListener('focus', onOnline);
    };
  }, [attemptId, sessionToken, intervalMs, maxRetries, persistSnapshot]);

  return {
    heartbeatNow: useCallback(() => {
      triggerRef.current();
    }, []),
  };
}
