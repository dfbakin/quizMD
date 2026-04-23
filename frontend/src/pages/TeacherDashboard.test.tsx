import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

import TeacherDashboard from './TeacherDashboard';
import { AuthProvider } from '../hooks/useAuth';
import { quizApi, groupApi, assignmentApi } from '../api/endpoints';
import type { AssignmentOut, GroupOut, QuizSummary } from '../types/quiz';

function seedAuth() {
  localStorage.setItem('access_token', 'tok');
  localStorage.setItem(
    'user',
    JSON.stringify({ user_id: 1, display_name: 'T', role: 'teacher' }),
  );
}

const QUIZ: QuizSummary = {
  id: 7,
  title: 'Algebra',
  time_limit_minutes: 30,
  shuffle_questions: false,
  shuffle_answers: false,
  question_count: 5,
  created_at: '2026-04-01T10:00:00Z',
};

const GROUP: GroupOut = { id: 5, name: '10-A', student_count: 12 };

const ASSIGNMENT: AssignmentOut = {
  id: 99,
  quiz_id: 7,
  group_id: 5,
  starts_at: '2026-04-23T08:00:00Z',
  ends_at: '2026-04-23T09:00:00Z',
  start_window_minutes: 60,
  duration_minutes: 60,
  shared_deadline: false,
  results_visible: false,
  student_view_mode: 'closed',
  quiz_title: 'Algebra',
  group_name: '10-A',
  share_code: 'abcd1234',
  in_progress_attempts: 0,
};

const SHARED_ASSIGNMENT: AssignmentOut = {
  ...ASSIGNMENT,
  id: 100,
  shared_deadline: true,
};

function renderDashboard(initialEntry = '/teacher') {
  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={[initialEntry]}>
        <TeacherDashboard />
      </MemoryRouter>
    </AuthProvider>,
  );
}

describe('TeacherDashboard URL-driven tabs', () => {
  beforeEach(() => {
    localStorage.clear();
    seedAuth();
    vi.spyOn(quizApi, 'list').mockResolvedValue({ data: [QUIZ] } as never);
    vi.spyOn(groupApi, 'list').mockResolvedValue({ data: [GROUP] } as never);
    vi.spyOn(assignmentApi, 'list').mockResolvedValue({
      data: [ASSIGNMENT],
    } as never);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('defaults to the quizzes tab when ?tab is missing', async () => {
    renderDashboard('/teacher');
    await waitFor(() =>
      expect(screen.getByRole('tab', { name: 'Тесты' })).toHaveAttribute(
        'aria-selected',
        'true',
      ),
    );
  });

  it('honors ?tab=groups in the URL', async () => {
    renderDashboard('/teacher?tab=groups');
    await waitFor(() =>
      expect(screen.getByRole('tab', { name: 'Группы' })).toHaveAttribute(
        'aria-selected',
        'true',
      ),
    );
    expect(screen.getByText('10-A')).toBeInTheDocument();
  });

  it('clicking a tab updates the active tab and URL', async () => {
    const user = userEvent.setup();
    renderDashboard('/teacher');
    await waitFor(() => screen.getByRole('tab', { name: 'Назначения' }));

    await user.click(screen.getByRole('tab', { name: 'Назначения' }));
    await waitFor(() =>
      expect(
        screen.getByRole('tab', { name: 'Назначения' }),
      ).toHaveAttribute('aria-selected', 'true'),
    );
  });

  it('falls back to the default tab on an invalid ?tab', async () => {
    renderDashboard('/teacher?tab=nonsense');
    await waitFor(() =>
      expect(screen.getByRole('tab', { name: 'Тесты' })).toHaveAttribute(
        'aria-selected',
        'true',
      ),
    );
  });
});

describe('TeacherDashboard nav buttons render as <a> Links (open-in-new-tab support)', () => {
  beforeEach(() => {
    localStorage.clear();
    seedAuth();
    vi.spyOn(quizApi, 'list').mockResolvedValue({ data: [QUIZ] } as never);
    vi.spyOn(groupApi, 'list').mockResolvedValue({ data: [GROUP] } as never);
    vi.spyOn(assignmentApi, 'list').mockResolvedValue({
      data: [ASSIGNMENT],
    } as never);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('quiz card "Подробнее" is a Link to /teacher/quiz/:id', async () => {
    renderDashboard('/teacher?tab=quizzes');
    const link = await screen.findByRole('link', { name: 'Подробнее' });
    expect(link).toHaveAttribute('href', '/teacher/quiz/7');
  });

  it('group card "Ученики" is a Link to /teacher/group/:id', async () => {
    renderDashboard('/teacher?tab=groups');
    const link = await screen.findByRole('link', { name: 'Ученики' });
    expect(link).toHaveAttribute('href', '/teacher/group/5');
  });

  it('assignment "Результаты" is a Link to /teacher/assignment/:id/results', async () => {
    renderDashboard('/teacher?tab=assignments');
    const link = await screen.findByRole('link', { name: 'Результаты' });
    expect(link).toHaveAttribute('href', '/teacher/assignment/99/results');
  });
});

describe('TeacherDashboard starts_at edit gating', () => {
  beforeEach(() => {
    localStorage.clear();
    seedAuth();
    vi.spyOn(quizApi, 'list').mockResolvedValue({ data: [QUIZ] } as never);
    vi.spyOn(groupApi, 'list').mockResolvedValue({ data: [GROUP] } as never);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('saves directly without prompting when there are zero in-progress attempts', async () => {
    vi.spyOn(assignmentApi, 'list').mockResolvedValue({
      data: [{ ...ASSIGNMENT, in_progress_attempts: 0 }],
    } as never);
    const update = vi.spyOn(assignmentApi, 'update').mockResolvedValue({
      data: { ...ASSIGNMENT, starts_at: '2026-04-25T08:00:00Z' },
    } as never);

    const user = userEvent.setup();
    renderDashboard('/teacher?tab=assignments');

    const editButtons = await screen.findAllByRole('button', { name: 'Изменить' });
    // Order on the card: Старт, Длительность попытки, Окно запуска.
    await user.click(editButtons[0]);
    await user.click(screen.getByRole('button', { name: 'Сохранить' }));

    await waitFor(() => expect(update).toHaveBeenCalled());
    const [, payload] = update.mock.calls[0];
    expect(payload).not.toHaveProperty('on_open_attempts');
  });

  it('opens the explicit reset/keep modal when there are in-progress attempts', async () => {
    vi.spyOn(assignmentApi, 'list').mockResolvedValue({
      data: [{ ...ASSIGNMENT, in_progress_attempts: 3 }],
    } as never);
    const update = vi.spyOn(assignmentApi, 'update').mockResolvedValue({
      data: { ...ASSIGNMENT, starts_at: '2026-04-25T08:00:00Z' },
    } as never);

    const user = userEvent.setup();
    renderDashboard('/teacher?tab=assignments');

    const editStartButtons = await screen.findAllByRole('button', { name: 'Изменить' });
    // Order on the card: Старт, Длительность попытки, Окно запуска. Use the
    // first one — the start-time editor.
    await user.click(editStartButtons[0]);
    await user.click(screen.getByRole('button', { name: 'Сохранить' }));

    expect(
      await screen.findByRole('dialog', { name: 'Что делать с активными попытками?' }),
    ).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Сохранить попытки' }));
    await waitFor(() => expect(update).toHaveBeenCalled());
    const [, payload] = update.mock.calls[0];
    expect(payload).toMatchObject({ on_open_attempts: 'keep' });
  });
});

describe('TeacherDashboard start_window_minutes UI', () => {
  beforeEach(() => {
    localStorage.clear();
    seedAuth();
    vi.spyOn(quizApi, 'list').mockResolvedValue({ data: [QUIZ] } as never);
    vi.spyOn(groupApi, 'list').mockResolvedValue({ data: [GROUP] } as never);
    vi.spyOn(assignmentApi, 'list').mockResolvedValue({
      data: [ASSIGNMENT],
    } as never);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders the start-window field on the create form', async () => {
    renderDashboard('/teacher?tab=assignments');
    expect(
      await screen.findByLabelText('Окно запуска'),
    ).toBeInTheDocument();
    expect(screen.getByLabelText('Длительность попытки')).toBeInTheDocument();
  });

  it('shows the assignment start_window_minutes on each card', async () => {
    renderDashboard('/teacher?tab=assignments');
    expect(
      await screen.findByText(/Окно запуска:\s*60\s*мин/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Длительность попытки:\s*60\s*мин/i),
    ).toBeInTheDocument();
  });

  it('inline-edits start_window_minutes and only sends that field', async () => {
    const update = vi.spyOn(assignmentApi, 'update').mockResolvedValue({
      data: { ...ASSIGNMENT, start_window_minutes: 120 },
    } as never);

    const user = userEvent.setup();
    renderDashboard('/teacher?tab=assignments');

    const editButtons = await screen.findAllByRole('button', { name: 'Изменить' });
    // Card order: Старт, Длительность попытки, Окно запуска. Pick the third.
    await user.click(editButtons[2]);

    const inputs = screen.getAllByRole('textbox');
    // The single textbox that just appeared is the start-window editor.
    const editor = inputs[inputs.length - 1];
    await user.clear(editor);
    await user.type(editor, '120');

    await user.click(screen.getByRole('button', { name: 'Сохранить' }));

    await waitFor(() => expect(update).toHaveBeenCalled());
    const [, payload] = update.mock.calls[0];
    expect(payload).toEqual({ start_window_minutes: 120 });
  });
});

describe('TeacherDashboard shared_deadline mode', () => {
  beforeEach(() => {
    localStorage.clear();
    seedAuth();
    vi.spyOn(quizApi, 'list').mockResolvedValue({ data: [QUIZ] } as never);
    vi.spyOn(groupApi, 'list').mockResolvedValue({ data: [GROUP] } as never);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders the deadline-mode segmented control on the create form', async () => {
    vi.spyOn(assignmentApi, 'list').mockResolvedValue({
      data: [ASSIGNMENT],
    } as never);
    renderDashboard('/teacher?tab=assignments');

    const personal = await screen.findByRole('radio', { name: 'Индивидуальный таймер' });
    const shared = screen.getByRole('radio', { name: 'Единый дедлайн' });
    expect(personal).toHaveAttribute('aria-checked', 'true');
    expect(shared).toHaveAttribute('aria-checked', 'false');
  });

  it('hides the start-window field when "Единый дедлайн" is selected', async () => {
    vi.spyOn(assignmentApi, 'list').mockResolvedValue({
      data: [ASSIGNMENT],
    } as never);
    const user = userEvent.setup();
    renderDashboard('/teacher?tab=assignments');

    expect(await screen.findByLabelText('Окно запуска')).toBeInTheDocument();

    await user.click(screen.getByRole('radio', { name: 'Единый дедлайн' }));

    expect(screen.queryByLabelText('Окно запуска')).not.toBeInTheDocument();
    expect(
      screen.getByText(/Окно запуска = длительности попытки/i),
    ).toBeInTheDocument();
  });

  it('shows the per-student pill on the card by default', async () => {
    vi.spyOn(assignmentApi, 'list').mockResolvedValue({
      data: [ASSIGNMENT],
    } as never);
    renderDashboard('/teacher?tab=assignments');

    expect(
      await screen.findByRole('button', { name: 'Индивидуальный таймер' }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Окно запуска:\s*60\s*мин/i),
    ).toBeInTheDocument();
  });

  it('shows the shared-deadline pill on shared-mode cards and hides start-window', async () => {
    vi.spyOn(assignmentApi, 'list').mockResolvedValue({
      data: [SHARED_ASSIGNMENT],
    } as never);
    renderDashboard('/teacher?tab=assignments');

    expect(
      await screen.findByRole('button', { name: 'Единый дедлайн' }),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Окно запуска:/i)).not.toBeInTheDocument();
    // The card switches to a wall-clock deadline label.
    expect(screen.getByText(/Дедлайн для всех:/i)).toBeInTheDocument();
  });

  it('clicking the mode pill flips shared_deadline via the API', async () => {
    vi.spyOn(assignmentApi, 'list').mockResolvedValue({
      data: [ASSIGNMENT],
    } as never);
    const update = vi.spyOn(assignmentApi, 'update').mockResolvedValue({
      data: SHARED_ASSIGNMENT,
    } as never);

    const user = userEvent.setup();
    renderDashboard('/teacher?tab=assignments');

    const pill = await screen.findByRole('button', { name: 'Индивидуальный таймер' });
    await user.click(pill);

    await waitFor(() => expect(update).toHaveBeenCalled());
    const [id, payload] = update.mock.calls[0];
    expect(id).toBe(99);
    expect(payload).toEqual({ shared_deadline: true });
    // After the API resolves the card re-renders with the new pill label.
    expect(
      await screen.findByRole('button', { name: 'Единый дедлайн' }),
    ).toBeInTheDocument();
  });

  it('create with shared mode omits start_window_minutes from the payload', async () => {
    vi.spyOn(assignmentApi, 'list').mockResolvedValue({ data: [] } as never);
    const create = vi.spyOn(assignmentApi, 'create').mockResolvedValue({
      data: SHARED_ASSIGNMENT,
    } as never);

    const user = userEvent.setup();
    renderDashboard('/teacher?tab=assignments');

    await user.click(await screen.findByRole('radio', { name: 'Единый дедлайн' }));

    // SearchSelect renders plain <input>; pick by placeholder.
    const quizInput = screen.getByPlaceholderText('Поиск теста...');
    await user.click(quizInput);
    await user.click(await screen.findByText('Algebra'));
    const groupInput = screen.getByPlaceholderText('Поиск группы...');
    await user.click(groupInput);
    await user.click(await screen.findByText('10-A'));

    // The datetime-local input has no accessible name in the markup.
    const dt = document.querySelector<HTMLInputElement>('input[type="datetime-local"]')!;
    await user.type(dt, '2026-05-01T09:00');

    await user.click(screen.getByRole('button', { name: 'Назначить' }));

    await waitFor(() => expect(create).toHaveBeenCalled());
    const payload = create.mock.calls[0][0];
    expect(payload).toMatchObject({
      quiz_id: 7,
      group_id: 5,
      duration_minutes: 45,
      shared_deadline: true,
    });
    // In shared mode we never send start_window_minutes — the server pins it.
    expect(payload).not.toHaveProperty('start_window_minutes');
  });
});
