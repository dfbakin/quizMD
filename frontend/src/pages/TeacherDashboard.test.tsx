import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

import TeacherDashboard from './TeacherDashboard';
import { AuthProvider } from '../hooks/useAuth';
import { quizApi, groupApi, assignmentApi, teacherApi } from '../api/endpoints';
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
  extra_student_count: 0,
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

// ---------------------------------------------------------------------------
// Filter bar (Quiz, Group, Status, search, collapse-by-quiz, URL-synced)
// ---------------------------------------------------------------------------
describe('TeacherDashboard filter bar', () => {
  // Two quizzes + two groups + four assignments is enough to exercise every
  // filter dimension without cross-pollution.
  const QUIZ_A: QuizSummary = { ...QUIZ, id: 7, title: 'Algebra' };
  const QUIZ_G: QuizSummary = { ...QUIZ, id: 8, title: 'Geometry' };
  const GROUP_A: GroupOut = { id: 5, name: '10-A', student_count: 10 };
  const GROUP_B: GroupOut = { id: 6, name: '10-B', student_count: 11 };

  // One card per (quiz × group) combination — 2×2 = 4 cards total.
  const a1: AssignmentOut = {
    ...ASSIGNMENT,
    id: 101,
    quiz_id: QUIZ_A.id,
    group_id: GROUP_A.id,
    quiz_title: QUIZ_A.title,
    group_name: GROUP_A.name,
  };
  const a2: AssignmentOut = {
    ...ASSIGNMENT,
    id: 102,
    quiz_id: QUIZ_A.id,
    group_id: GROUP_B.id,
    quiz_title: QUIZ_A.title,
    group_name: GROUP_B.name,
  };
  const a3: AssignmentOut = {
    ...ASSIGNMENT,
    id: 103,
    quiz_id: QUIZ_G.id,
    group_id: GROUP_A.id,
    quiz_title: QUIZ_G.title,
    group_name: GROUP_A.name,
  };
  const a4: AssignmentOut = {
    ...ASSIGNMENT,
    id: 104,
    quiz_id: QUIZ_G.id,
    group_id: GROUP_B.id,
    quiz_title: QUIZ_G.title,
    group_name: GROUP_B.name,
  };

  beforeEach(() => {
    localStorage.clear();
    seedAuth();
    vi.spyOn(quizApi, 'list').mockResolvedValue({ data: [QUIZ_A, QUIZ_G] } as never);
    vi.spyOn(groupApi, 'list').mockResolvedValue({ data: [GROUP_A, GROUP_B] } as never);
    vi.spyOn(assignmentApi, 'list').mockResolvedValue({
      data: [a1, a2, a3, a4],
    } as never);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders all cards with no active filter', async () => {
    renderDashboard('/teacher?tab=assignments');
    expect(await screen.findAllByText('Результаты')).toHaveLength(4);
  });

  it('filters by a single quiz via the quiz popover', async () => {
    const user = userEvent.setup();
    renderDashboard('/teacher?tab=assignments');
    await screen.findAllByText('Результаты');

    await user.click(screen.getByRole('button', { name: /^Тесты/i }));
    // Algebra appears twice in the DOM (filter option + the card), so limit
    // selection to the listbox option element.
    await user.click(await screen.findByRole('option', { name: 'Algebra' }));

    await waitFor(() =>
      expect(screen.getAllByText('Результаты')).toHaveLength(2),
    );
  });

  it('free-text search matches quiz title', async () => {
    const user = userEvent.setup();
    renderDashboard('/teacher?tab=assignments');
    await screen.findAllByText('Результаты');

    const search = screen.getByPlaceholderText(/Поиск по названию/i);
    await user.type(search, 'Geo');

    await waitFor(() =>
      expect(screen.getAllByText('Результаты')).toHaveLength(2),
    );
  });

  it('clearing all filters restores the full list', async () => {
    const user = userEvent.setup();
    renderDashboard('/teacher?tab=assignments&q=Algebra');
    await waitFor(() =>
      expect(screen.getAllByText('Результаты')).toHaveLength(2),
    );

    await user.click(screen.getByRole('button', { name: 'Сбросить' }));
    await waitFor(() =>
      expect(screen.getAllByText('Результаты')).toHaveLength(4),
    );
  });

  it('honors ?quiz=<id> deep-link on first load', async () => {
    renderDashboard(`/teacher?tab=assignments&quiz=${QUIZ_G.id}`);
    await waitFor(() =>
      expect(screen.getAllByText('Результаты')).toHaveLength(2),
    );
  });

  it('collapse-by-quiz groups cards under bucket headers', async () => {
    const user = userEvent.setup();
    renderDashboard('/teacher?tab=assignments');
    await screen.findAllByText('Результаты');

    await user.click(screen.getByLabelText(/Группировать по тесту/));

    // Each of the two quizzes should show as a bucket heading with count "· 2".
    await waitFor(() => {
      expect(screen.getAllByText(/· 2/).length).toBeGreaterThanOrEqual(2);
    });
  });
});

// ---------------------------------------------------------------------------
// Per-card extras editor (AssignmentExtraStudent CRUD via the row UI)
// ---------------------------------------------------------------------------
describe('TeacherDashboard AssignmentExtrasEditor', () => {
  beforeEach(() => {
    localStorage.clear();
    seedAuth();
    vi.spyOn(quizApi, 'list').mockResolvedValue({ data: [QUIZ] } as never);
    vi.spyOn(groupApi, 'list').mockResolvedValue({ data: [GROUP] } as never);
    vi.spyOn(assignmentApi, 'list').mockResolvedValue({
      data: [{ ...ASSIGNMENT, extra_student_count: 1 }],
    } as never);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('shows the +N badge and lazy-loads the list on expand', async () => {
    const listExtras = vi
      .spyOn(assignmentApi, 'listExtras')
      .mockResolvedValue({
        data: [
          {
            id: 77,
            display_name: 'Иванов Иван',
            username: 'ivanov',
            home_group_id: 6,
            home_group_name: '10-B',
          },
        ],
      } as never);

    const user = userEvent.setup();
    renderDashboard('/teacher?tab=assignments');
    expect(await screen.findByText('+1')).toBeInTheDocument();
    expect(listExtras).not.toHaveBeenCalled();

    await user.click(
      screen.getByRole('button', { name: /Дополнительные ученики/ }),
    );
    await waitFor(() => expect(listExtras).toHaveBeenCalledWith(99));
    expect(await screen.findByText(/Иванов Иван/)).toBeInTheDocument();
  });

  it('remove chip calls removeExtra and drops the row optimistically', async () => {
    vi.spyOn(assignmentApi, 'listExtras').mockResolvedValue({
      data: [
        {
          id: 77,
          display_name: 'Иванов Иван',
          username: 'ivanov',
          home_group_id: 6,
          home_group_name: '10-B',
        },
      ],
    } as never);
    const removeExtra = vi
      .spyOn(assignmentApi, 'removeExtra')
      .mockResolvedValue({} as never);

    const user = userEvent.setup();
    renderDashboard('/teacher?tab=assignments');
    await user.click(
      await screen.findByRole('button', { name: /Дополнительные ученики/ }),
    );
    await screen.findByText(/Иванов Иван/);

    await user.click(screen.getByRole('button', { name: /Убрать Иванов Иван/ }));
    await waitFor(() => expect(removeExtra).toHaveBeenCalledWith(99, 77));
    await waitFor(() =>
      expect(screen.queryByText(/Иванов Иван/)).not.toBeInTheDocument(),
    );
  });

  it('picker hides students already in the home group or already added', async () => {
    vi.spyOn(assignmentApi, 'listExtras').mockResolvedValue({
      data: [
        {
          id: 77,
          display_name: 'Иванов Иван',
          username: 'ivanov',
          home_group_id: 6,
          home_group_name: '10-B',
        },
      ],
    } as never);
    // Three search hits:
    //   - 77 already-added → filtered
    //   - 88 home-group (group_id = 5 === ASSIGNMENT.group_id) → filtered
    //   - 99 from a different group → should show up
    vi.spyOn(teacherApi, 'searchMyStudents').mockResolvedValue({
      data: [
        {
          id: 77,
          display_name: 'Иванов Иван',
          username: 'ivanov',
          group_id: 6,
          group_name: '10-B',
        },
        {
          id: 88,
          display_name: 'Петров Пётр',
          username: 'petrov',
          group_id: 5,
          group_name: '10-A',
        },
        {
          id: 99,
          display_name: 'Сидоров Сидр',
          username: 'sidorov',
          group_id: 7,
          group_name: '10-C',
        },
      ],
    } as never);

    const user = userEvent.setup();
    renderDashboard('/teacher?tab=assignments');
    await user.click(
      await screen.findByRole('button', { name: /Дополнительные ученики/ }),
    );
    await user.click(
      await screen.findByRole('button', { name: /Добавить ученика/ }),
    );

    // Sidorov should appear (different group, not added yet). Only him.
    expect(await screen.findByText(/Сидоров/)).toBeInTheDocument();
    expect(screen.queryByText(/Петров/)).not.toBeInTheDocument();
    // Ivanov still appears as a CHIP (removed button) but not as a picker row —
    // the picker row would be a <button role=menuitem>-style element, not a chip.
    expect(screen.queryByRole('button', { name: /^Сидоров/ })).toBeInTheDocument();
  });

  it('add flow calls addExtra and refreshes the list', async () => {
    const listExtras = vi.spyOn(assignmentApi, 'listExtras');
    listExtras
      .mockResolvedValueOnce({ data: [] } as never)
      .mockResolvedValueOnce({
        data: [
          {
            id: 99,
            display_name: 'Сидоров Сидр',
            username: 'sidorov',
            home_group_id: 7,
            home_group_name: '10-C',
          },
        ],
      } as never);
    const addExtra = vi
      .spyOn(assignmentApi, 'addExtra')
      .mockResolvedValue({
        data: {
          id: 99,
          display_name: 'Сидоров Сидр',
          username: 'sidorov',
          home_group_id: 7,
          home_group_name: '10-C',
        },
      } as never);
    vi.spyOn(teacherApi, 'searchMyStudents').mockResolvedValue({
      data: [
        {
          id: 99,
          display_name: 'Сидоров Сидр',
          username: 'sidorov',
          group_id: 7,
          group_name: '10-C',
        },
      ],
    } as never);

    const user = userEvent.setup();
    renderDashboard('/teacher?tab=assignments');
    await user.click(
      await screen.findByRole('button', { name: /Дополнительные ученики/ }),
    );
    await user.click(
      await screen.findByRole('button', { name: /Добавить ученика/ }),
    );
    await user.click(await screen.findByRole('button', { name: /^Сидоров/ }));

    await waitFor(() => expect(addExtra).toHaveBeenCalledWith(99, 99));
    // listExtras gets called twice: once on expand, once after successful add.
    await waitFor(() => expect(listExtras).toHaveBeenCalledTimes(2));
  });
});
