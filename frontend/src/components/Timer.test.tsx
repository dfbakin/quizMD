import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render, screen } from '@testing-library/react';

import Timer from './Timer';

/**
 * The Timer is the home of Bug E. Two regression tests are critical:
 *  1. Display ticks down based on the monotonic clock, never on Date.now()
 *     (so wall-clock changes don't disturb it).
 *  2. The displayed remaining time does NOT reset when the parent re-renders
 *     with a new `onExpire` callback identity (the keystroke shape).
 */
describe('Timer (server-authoritative, RAF-driven)', () => {
  let perfNow = 0;
  const rafCallbacks: Array<{ id: number; cb: FrameRequestCallback }> = [];
  let nextRafId = 1;

  beforeEach(() => {
    perfNow = 0;
    rafCallbacks.length = 0;
    nextRafId = 1;
    vi.spyOn(performance, 'now').mockImplementation(() => perfNow);
    vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => {
      const id = nextRafId++;
      rafCallbacks.push({ id, cb });
      return id;
    });
    vi.stubGlobal('cancelAnimationFrame', (id: number) => {
      const idx = rafCallbacks.findIndex((r) => r.id === id);
      if (idx >= 0) rafCallbacks.splice(idx, 1);
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  /** Advance perf.now and flush every queued RAF callback once. */
  const advance = (ms: number) => {
    perfNow += ms;
    act(() => {
      const pending = rafCallbacks.splice(0, rafCallbacks.length);
      for (const { cb } of pending) cb(perfNow);
    });
  };

  it('displays the countdown anchored to server time', () => {
    const serverNow = '2026-04-23T10:00:00.000Z';
    const deadlineAt = '2026-04-23T10:01:00.000Z';
    render(<Timer deadlineAt={deadlineAt} serverNowAtAnchor={serverNow} onExpire={() => {}} />);

    advance(0);
    expect(screen.getByTestId('quiz-timer')).toHaveTextContent('01:00');

    advance(1000);
    expect(screen.getByTestId('quiz-timer')).toHaveTextContent('00:59');

    advance(58000);
    expect(screen.getByTestId('quiz-timer')).toHaveTextContent('00:01');
  });

  it('does NOT reset when parent re-renders with a new onExpire identity (Bug E)', () => {
    const serverNow = '2026-04-23T10:00:00.000Z';
    const deadlineAt = '2026-04-23T10:01:00.000Z';

    const { rerender } = render(
      <Timer
        deadlineAt={deadlineAt}
        serverNowAtAnchor={serverNow}
        onExpire={() => {}}
      />,
    );

    advance(15_000);
    expect(screen.getByTestId('quiz-timer')).toHaveTextContent('00:45');

    // Simulate the keystroke pattern: parent passes a brand-new callback
    // identity on every render (e.g. an inline arrow), but neither
    // deadlineAt nor serverNowAtAnchor changes.
    for (let i = 0; i < 5; i++) {
      rerender(
        <Timer
          deadlineAt={deadlineAt}
          serverNowAtAnchor={serverNow}
          onExpire={() => `keystroke-${i}`}
        />,
      );
    }

    advance(0);
    // Display must still be ~45s remaining, not reset to 60s.
    expect(screen.getByTestId('quiz-timer')).toHaveTextContent('00:45');

    advance(5000);
    expect(screen.getByTestId('quiz-timer')).toHaveTextContent('00:40');
  });

  it('re-anchors smoothly when serverNowAtAnchor changes', () => {
    const deadlineAt = '2026-04-23T10:01:00.000Z';
    const { rerender } = render(
      <Timer
        deadlineAt={deadlineAt}
        serverNowAtAnchor={'2026-04-23T10:00:00.000Z'}
        onExpire={() => {}}
      />,
    );

    advance(0);
    expect(screen.getByTestId('quiz-timer')).toHaveTextContent('01:00');

    // Local clock has advanced 10s, but a fresh heartbeat says the server
    // is now 20s in. The timer should re-anchor and reflect 40s remaining,
    // not 50s.
    advance(10_000);
    rerender(
      <Timer
        deadlineAt={deadlineAt}
        serverNowAtAnchor={'2026-04-23T10:00:20.000Z'}
        onExpire={() => {}}
      />,
    );
    advance(0);
    expect(screen.getByTestId('quiz-timer')).toHaveTextContent('00:40');
  });

  it('calls onExpire exactly once when the deadline passes', () => {
    const onExpire = vi.fn();
    render(
      <Timer
        deadlineAt={'2026-04-23T10:00:05.000Z'}
        serverNowAtAnchor={'2026-04-23T10:00:00.000Z'}
        onExpire={onExpire}
      />,
    );

    advance(4000);
    expect(onExpire).not.toHaveBeenCalled();

    advance(2000);
    expect(onExpire).toHaveBeenCalledTimes(1);

    advance(5000);
    expect(onExpire).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId('quiz-timer')).toHaveTextContent('Время вышло');
  });
});
