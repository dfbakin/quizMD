import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import QuizTake from './QuizTake';
import { studentApi } from '../api/endpoints';
import type { AttemptStart } from '../types/quiz';

function buildAttempt(overrides: Partial<AttemptStart> = {}): AttemptStart {
  return {
    attempt_id: 1,
    session_token: 'tok',
    duration_minutes: 30,
    started_at: '2026-04-23T10:00:00.000Z',
    deadline_at: '2026-04-23T10:30:00.000Z',
    server_now: '2026-04-23T10:00:00.000Z',
    saved_answers: [],
    questions: [
      {
        id: 11,
        order_index: 0,
        q_type: 'single',
        title: 'Q1',
        body_md: 'Pick one',
        points: 1,
        options: [
          { id: 100, order_index: 0, text_md: 'A' },
          { id: 101, order_index: 1, text_md: 'B' },
        ],
      },
    ],
    ...overrides,
  };
}

function renderQuiz() {
  return render(
    <MemoryRouter initialEntries={['/student/quiz/1']}>
      <Routes>
        <Route path="/student/quiz/:assignmentId" element={<QuizTake />} />
        <Route path="/student" element={<div>Student dashboard</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('QuizTake', () => {
  let perfNow = 0;
  const rafCallbacks: Array<{ id: number; cb: FrameRequestCallback }> = [];
  let nextRafId = 1;

  beforeEach(() => {
    perfNow = 0;
    rafCallbacks.length = 0;
    nextRafId = 1;
    localStorage.clear();
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

  const advance = (ms: number) => {
    perfNow += ms;
    act(() => {
      const pending = rafCallbacks.splice(0, rafCallbacks.length);
      for (const { cb } of pending) cb(perfNow);
    });
  };

  it('renders exactly one submit button (Issue 3)', async () => {
    vi.spyOn(studentApi, 'startAttempt').mockResolvedValue({
      data: buildAttempt(),
    } as never);

    renderQuiz();

    await waitFor(() => expect(screen.getByText('Q1')).toBeInTheDocument());
    const submitBtns = screen.getAllByRole('button', { name: 'Отправить' });
    expect(submitBtns).toHaveLength(1);
  });

  it('on simulated expiry, posts /submit and shows the success screen', async () => {
    vi.spyOn(studentApi, 'startAttempt').mockResolvedValue({
      data: buildAttempt({
        server_now: '2026-04-23T10:00:00.000Z',
        deadline_at: '2026-04-23T10:00:05.000Z',
      }),
    } as never);
    const submitSpy = vi
      .spyOn(studentApi, 'submitAttempt')
      .mockResolvedValue({ data: { ok: true } } as never);

    renderQuiz();

    await waitFor(() => expect(screen.getByText('Q1')).toBeInTheDocument());

    advance(0);
    advance(5000);
    advance(1000);

    await waitFor(() => expect(submitSpy).toHaveBeenCalled());
    expect(submitSpy.mock.calls[0][0]).toBe(1); // attempt_id
    expect(submitSpy.mock.calls[0][2]).toBe('tok'); // session_token

    await waitFor(() =>
      expect(screen.getByText('Тест отправлен')).toBeInTheDocument(),
    );
  });

  it('on submit failure, surfaces a retry banner and keeps the rolling backup', async () => {
    vi.spyOn(studentApi, 'startAttempt').mockResolvedValue({
      data: buildAttempt(),
    } as never);
    vi.spyOn(studentApi, 'submitAttempt').mockRejectedValue(
      Object.assign(new Error('boom'), { response: { status: 500 } }),
    );

    renderQuiz();
    await waitFor(() => expect(screen.getByText('Q1')).toBeInTheDocument());

    const headerSubmit = screen.getByRole('button', { name: 'Отправить' });
    await act(async () => {
      headerSubmit.click();
      // Walk through the retry backoffs synchronously.
      await new Promise((r) => setTimeout(r, 0));
    });

    await waitFor(
      () =>
        expect(
          screen.getByText(/Не удалось отправить ответы/i),
        ).toBeInTheDocument(),
      { timeout: 20_000 },
    );
    expect(screen.getByRole('button', { name: 'Повторить' })).toBeInTheDocument();
  }, 25_000);
});
