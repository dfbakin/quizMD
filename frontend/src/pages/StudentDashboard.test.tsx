import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import StudentDashboard from './StudentDashboard';
import { AuthProvider } from '../hooks/useAuth';
import { studentApi } from '../api/endpoints';
import type { StudentAssignment } from '../types/quiz';

function seedAuth() {
  localStorage.setItem('access_token', 'tok');
  localStorage.setItem(
    'user',
    JSON.stringify({ user_id: 1, display_name: 'S', role: 'student' }),
  );
}

const ACTIVE: StudentAssignment = {
  assignment_id: 11,
  quiz_title: 'Algebra',
  starts_at: '2026-04-23T08:00:00Z',
  ends_at: '2026-04-23T09:00:00Z',
  start_window_minutes: 60,
  duration_minutes: 60,
  shared_deadline: false,
  status: 'active',
  attempt_id: null,
  attempt_deadline_at: null,
  results_visible: false,
  student_view_mode: 'closed',
};

const COMPLETED: StudentAssignment = {
  assignment_id: 12,
  quiz_title: 'Geometry',
  starts_at: '2026-04-22T08:00:00Z',
  ends_at: '2026-04-22T09:00:00Z',
  start_window_minutes: 30,
  duration_minutes: 30,
  shared_deadline: false,
  status: 'completed',
  attempt_id: 222,
  attempt_deadline_at: '2026-04-22T08:30:00Z',
  results_visible: true,
  student_view_mode: 'results',
};

const ACTIVE_SHARED: StudentAssignment = {
  ...ACTIVE,
  assignment_id: 13,
  quiz_title: 'Trigonometry',
  shared_deadline: true,
};

function renderDashboard() {
  return render(
    <AuthProvider>
      <MemoryRouter>
        <StudentDashboard />
      </MemoryRouter>
    </AuthProvider>,
  );
}

describe('StudentDashboard nav buttons render as <a> Links', () => {
  beforeEach(() => {
    localStorage.clear();
    seedAuth();
    vi.spyOn(studentApi, 'myAssignments').mockResolvedValue({
      data: [ACTIVE, COMPLETED],
    } as never);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('"Начать" / "Продолжить" is a Link to /student/quiz/:assignment_id', async () => {
    renderDashboard();
    const link = await screen.findByRole('link', { name: 'Начать' });
    expect(link).toHaveAttribute('href', '/student/quiz/11');
  });

  it('"Результаты" is a Link to /student/results/:attempt_id', async () => {
    renderDashboard();
    const link = await screen.findByRole('link', { name: 'Результаты' });
    expect(link).toHaveAttribute('href', '/student/results/222');
  });

  it('shows the per-attempt duration without referencing time_limit_minutes', async () => {
    renderDashboard();
    await waitFor(() =>
      expect(screen.getAllByText(/мин/i).length).toBeGreaterThan(0),
    );
    expect(screen.getByText(/Длительность попытки:\s*60\s*мин/i)).toBeInTheDocument();
    expect(screen.getByText(/Длительность попытки:\s*30\s*мин/i)).toBeInTheDocument();
  });

  it('shows "Можно начать до" using the start-window close (ends_at)', async () => {
    renderDashboard();
    const matches = await screen.findAllByText(/Можно начать до/);
    expect(matches.length).toBeGreaterThan(0);
  });

  it('shows "Доступен с" using the start time on every card', async () => {
    renderDashboard();
    const matches = await screen.findAllByText(/Доступен с /);
    expect(matches.length).toBe(2);
  });
});

describe('StudentDashboard shared_deadline mode labels', () => {
  beforeEach(() => {
    localStorage.clear();
    seedAuth();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('shows "Дедлайн для всех" instead of "Можно начать до" in shared mode', async () => {
    vi.spyOn(studentApi, 'myAssignments').mockResolvedValue({
      data: [ACTIVE_SHARED],
    } as never);
    renderDashboard();

    expect(await screen.findByText(/Дедлайн для всех:/)).toBeInTheDocument();
    expect(screen.queryByText(/Можно начать до/)).not.toBeInTheDocument();
    // The "duration of the test" label is used instead of "duration of the attempt"
    // — late starters get less time on the clock.
    expect(screen.getByText(/Длительность теста:\s*60\s*мин/i)).toBeInTheDocument();
  });

  it('still shows "Доступен с" in shared mode', async () => {
    vi.spyOn(studentApi, 'myAssignments').mockResolvedValue({
      data: [ACTIVE_SHARED],
    } as never);
    renderDashboard();

    expect(await screen.findByText(/Доступен с /)).toBeInTheDocument();
  });
});
