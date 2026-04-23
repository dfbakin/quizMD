import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render, waitFor } from '@testing-library/react';
import { useEffect } from 'react';

import { useHeartbeat } from './useHeartbeat';
import type { AnswerSave, HeartbeatResponse } from '../types/quiz';

interface HarnessProps {
  attemptId: number;
  sessionToken: string;
  getAnswers: () => AnswerSave[];
  send: (
    attemptId: number,
    sessionToken: string,
    answers: AnswerSave[],
  ) => Promise<HeartbeatResponse>;
  onAnchor?: (a: { serverNow: string; deadlineAt: string }) => void;
  onInvalidated?: () => void;
  onExpired?: (resp: HeartbeatResponse) => void;
  intervalMs?: number;
  maxRetries?: number;
  triggerOnMount?: boolean;
}

/** Test harness that triggers a single heartbeat on mount, synchronously. */
function HeartbeatHarness(props: HarnessProps) {
  const { heartbeatNow } = useHeartbeat({
    attemptId: props.attemptId,
    sessionToken: props.sessionToken,
    getAnswers: props.getAnswers,
    onAnchor: props.onAnchor ?? (() => {}),
    onInvalidated: props.onInvalidated,
    onExpired: props.onExpired,
    intervalMs: props.intervalMs ?? 30_000,
    maxRetries: props.maxRetries ?? 3,
    send: props.send,
  });

  useEffect(() => {
    if (props.triggerOnMount !== false) heartbeatNow();
  }, [heartbeatNow, props.triggerOnMount]);

  return null;
}

const okResp = (
  overrides: Partial<HeartbeatResponse> = {},
): HeartbeatResponse => ({
  server_now: '2026-04-23T10:00:00.000Z',
  deadline_at: '2026-04-23T10:30:00.000Z',
  status: 'in_progress',
  expired: false,
  score: null,
  ...overrides,
});

describe('useHeartbeat', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('sends ALL current answers (including cleared ones) on each heartbeat', async () => {
    const send = vi.fn(async () => okResp());
    const answers: AnswerSave[] = [
      { question_id: 1, selected_option_ids: [10] },
      { question_id: 2, selected_option_ids: [] }, // cleared — must be sent
      { question_id: 3, text_answer: '' },          // cleared — must be sent
    ];

    render(
      <HeartbeatHarness
        attemptId={42}
        sessionToken="tok"
        getAnswers={() => answers}
        send={send}
      />,
    );

    await waitFor(() => expect(send).toHaveBeenCalled());
    expect(send).toHaveBeenCalledWith(42, 'tok', answers);
  });

  it('forwards (server_now, deadline_at) to onAnchor on every successful response', async () => {
    const onAnchor = vi.fn();
    const send = vi.fn(async () =>
      okResp({
        server_now: '2026-04-23T10:05:00.000Z',
        deadline_at: '2026-04-23T10:35:00.000Z',
      }),
    );

    render(
      <HeartbeatHarness
        attemptId={1}
        sessionToken="t"
        getAnswers={() => []}
        send={send}
        onAnchor={onAnchor}
      />,
    );

    await waitFor(() => expect(onAnchor).toHaveBeenCalled());
    expect(onAnchor).toHaveBeenCalledWith({
      serverNow: '2026-04-23T10:05:00.000Z',
      deadlineAt: '2026-04-23T10:35:00.000Z',
    });
  });

  it('persists a localStorage snapshot keyed by attemptId on every send', async () => {
    const answers: AnswerSave[] = [{ question_id: 1, selected_option_ids: [10] }];
    const send = vi.fn(async () => okResp());

    render(
      <HeartbeatHarness
        attemptId={77}
        sessionToken="t"
        getAnswers={() => answers}
        send={send}
      />,
    );

    await waitFor(() => expect(send).toHaveBeenCalled());
    expect(localStorage.getItem('backup_77')).toBe(JSON.stringify(answers));
  });

  it('retries with backoff on transient errors', async () => {
    vi.useFakeTimers();
    try {
      const err = Object.assign(new Error('timeout'), { response: { status: 503 } });
      const send = vi
        .fn<NonNullable<HarnessProps['send']>>()
        .mockRejectedValueOnce(err)
        .mockRejectedValueOnce(err)
        .mockResolvedValueOnce(okResp());

      render(
        <HeartbeatHarness
          attemptId={1}
          sessionToken="t"
          getAnswers={() => []}
          send={send}
        />,
      );

      // Drain microtasks for the initial mount + first send + first reject.
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });
      expect(send).toHaveBeenCalledTimes(1);

      // First retry scheduled at ~500ms.
      await act(async () => {
        await vi.advanceTimersByTimeAsync(600);
      });
      expect(send).toHaveBeenCalledTimes(2);

      // Second retry scheduled at ~1000ms after the second failure.
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1100);
      });
      expect(send).toHaveBeenCalledTimes(3);
    } finally {
      vi.useRealTimers();
    }
  });

  it('signals onInvalidated on 404', async () => {
    const onInvalidated = vi.fn();
    const send = vi.fn(async () => {
      throw Object.assign(new Error('gone'), { response: { status: 404 } });
    });

    render(
      <HeartbeatHarness
        attemptId={1}
        sessionToken="t"
        getAnswers={() => []}
        send={send}
        onInvalidated={onInvalidated}
      />,
    );

    await waitFor(() => expect(onInvalidated).toHaveBeenCalledTimes(1));
    expect(send).toHaveBeenCalledTimes(1); // no retry on 404
  });

  it('signals onExpired when server reports expired:true', async () => {
    const onExpired = vi.fn();
    const send = vi.fn(async () =>
      okResp({ status: 'expired', expired: true, score: 5 }),
    );

    render(
      <HeartbeatHarness
        attemptId={1}
        sessionToken="t"
        getAnswers={() => []}
        send={send}
        onExpired={onExpired}
      />,
    );

    await waitFor(() => expect(onExpired).toHaveBeenCalledTimes(1));
    expect(onExpired.mock.calls[0][0].score).toBe(5);
  });
});
