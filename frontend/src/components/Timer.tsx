import { useEffect, useRef, useState } from 'react';

export interface TimerProps {
  /** ISO datetime, snapshotted on the server when the attempt started. */
  deadlineAt: string;
  /**
   * Server's notion of "now", from the most recent /start or /heartbeat
   * response. The Timer re-anchors its monotonic clock when (and only when)
   * this string changes — never on parent re-renders.
   */
  serverNowAtAnchor: string;
  /**
   * Called exactly once when remaining time hits zero. Identity may change
   * freely across renders (kept stable internally via a ref) — Bug E was
   * caused by re-anchoring on every callback identity change.
   */
  onExpire: () => void;
}

/**
 * Server-authoritative countdown timer.
 *
 * Design:
 *  - Anchor (serverNowMs, perfNowMs) on each new heartbeat. Any frame's
 *    estimated server-now is `anchor.serverNowMs + (performance.now() - anchor.perfNowMs)`.
 *  - performance.now() is monotonic and unaffected by user clock changes,
 *    NTP slews, or DST. Once anchored, drift is bounded by the heartbeat
 *    cadence (~30s).
 *  - We use requestAnimationFrame for the visual update loop. RAF is
 *    throttled while the tab is hidden, but that's harmless — the next
 *    visible frame will recompute from the same monotonic anchor.
 *  - onExpire is read through a ref, so a parent passing a new closure on
 *    every keystroke (the Bug E shape) does NOT cause re-anchoring.
 */
export default function Timer({ deadlineAt, serverNowAtAnchor, onExpire }: TimerProps) {
  const onExpireRef = useRef(onExpire);
  useEffect(() => {
    onExpireRef.current = onExpire;
  }, [onExpire]);

  const deadlineMs = Date.parse(deadlineAt);
  const serverNowMs = Date.parse(serverNowAtAnchor);

  // Anchor between the server's notion of "now" and our local monotonic clock.
  // Lazily set on mount (and updated whenever serverNowAtAnchor changes) so we
  // never invoke the impure performance.now() during render.
  const anchorRef = useRef<{ serverNowMs: number; perfNowMs: number } | null>(null);

  useEffect(() => {
    anchorRef.current = {
      serverNowMs,
      perfNowMs: typeof performance !== 'undefined' ? performance.now() : 0,
    };
  }, [serverNowMs]);

  const didExpireRef = useRef(false);
  useEffect(() => {
    didExpireRef.current = false;
  }, [deadlineMs]);

  // Initial value is derived purely from server timestamps — at t=0 there is
  // no monotonic drift to correct for, so the impure clock isn't needed yet.
  const [remaining, setRemaining] = useState<number>(() =>
    Math.max(0, Math.floor((deadlineMs - serverNowMs) / 1000)),
  );

  useEffect(() => {
    let cancelled = false;
    let rafId: number | null = null;
    let lastShown = -1;

    const tick = () => {
      if (cancelled) return;
      const anchor = anchorRef.current;
      const now = typeof performance !== 'undefined' ? performance.now() : 0;
      const serverNowEst = anchor ? anchor.serverNowMs + (now - anchor.perfNowMs) : serverNowMs;
      const r = Math.max(0, Math.floor((deadlineMs - serverNowEst) / 1000));
      if (r !== lastShown) {
        lastShown = r;
        setRemaining(r);
      }
      if (r <= 0 && !didExpireRef.current) {
        didExpireRef.current = true;
        onExpireRef.current();
      }
      rafId = requestAnimationFrame(tick);
    };
    rafId = requestAnimationFrame(tick);
    return () => {
      cancelled = true;
      if (rafId !== null) cancelAnimationFrame(rafId);
    };
  }, [deadlineMs, serverNowMs]);

  const mins = Math.floor(remaining / 60);
  const secs = remaining % 60;
  const isWarning = remaining <= 300 && remaining > 0;
  const isExpired = remaining <= 0;

  return (
    <div
      className={`font-mono text-lg font-bold px-4 py-2 rounded-lg ${
        isExpired
          ? 'bg-red-600 text-white'
          : isWarning
            ? 'bg-amber-500 text-white'
            : 'bg-blue-600 text-white'
      }`}
      data-testid="quiz-timer"
    >
      {isExpired
        ? 'Время вышло'
        : `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`}
    </div>
  );
}
