import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { quizApi, groupApi, assignmentApi } from '../api/endpoints';
import type { QuizSummary, GroupOut, AssignmentOut, StudentViewMode } from '../types/quiz';
import { useAuth } from '../hooks/useAuth';
import SearchSelect from '../components/SearchSelect';
import ThemeToggle from '../components/ThemeToggle';
import LatexText from '../components/LatexText';

type TeacherTab = 'quizzes' | 'groups' | 'assignments';
const TEACHER_TABS: TeacherTab[] = ['quizzes', 'groups', 'assignments'];

function parseTab(value: string | null): TeacherTab {
  return TEACHER_TABS.includes(value as TeacherTab) ? (value as TeacherTab) : 'quizzes';
}

function getApiErrorDetail(err: unknown): string | undefined {
  if (typeof err === 'object' && err !== null && 'response' in err) {
    const detail = (err as { response?: { data?: { detail?: unknown } } }).response?.data?.detail;
    if (typeof detail === 'string') return detail;
  }
  return undefined;
}

export default function TeacherDashboard() {
  const { user, logout } = useAuth();
  const [quizzes, setQuizzes] = useState<QuizSummary[]>([]);
  const [groups, setGroups] = useState<GroupOut[]>([]);
  const [assignments, setAssignments] = useState<AssignmentOut[]>([]);
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = useMemo(() => parseTab(searchParams.get('tab')), [searchParams]);

  const setTab = (next: TeacherTab) => {
    setSearchParams((prev) => {
      const sp = new URLSearchParams(prev);
      sp.set('tab', next);
      return sp;
    });
  };

  const reload = () => {
    quizApi.list().then((r) => setQuizzes(r.data));
    groupApi.list().then((r) => setGroups(r.data));
    assignmentApi.list().then((r) => setAssignments(r.data));
  };
  useEffect(reload, []);

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950">
      <header className="bg-white dark:bg-gray-900 shadow-sm border-b border-gray-200 dark:border-gray-700">
        <div className="max-w-5xl mx-auto px-4 py-4 flex justify-between items-center">
          <div>
            <h1 className="text-xl font-bold text-gray-800 dark:text-gray-100">Quiz Core — Панель учителя</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">{user?.display_name}</p>
          </div>
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <button onClick={logout} className="text-sm text-gray-500 dark:text-gray-400 hover:text-red-500 transition">Выйти</button>
          </div>
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-4 mt-6">
        <div role="tablist" className="flex gap-1 bg-gray-200 dark:bg-gray-700 rounded-lg p-1 mb-6">
          {TEACHER_TABS.map((t) => (
            <button
              key={t}
              role="tab"
              aria-selected={tab === t}
              onClick={() => setTab(t)}
              className={`flex-1 py-2 text-sm font-medium rounded-md transition ${
                tab === t ? 'bg-white dark:bg-gray-900 shadow text-gray-800 dark:text-gray-100' : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
              }`}
            >
              {t === 'quizzes' ? 'Тесты' : t === 'groups' ? 'Группы' : 'Назначения'}
            </button>
          ))}
        </div>

        {tab === 'quizzes' && (
          <QuizzesTab quizzes={quizzes} onReload={reload} />
        )}
        {tab === 'groups' && (
          <GroupsTab groups={groups} onReload={reload} />
        )}
        {tab === 'assignments' && (
          <AssignmentsTab
            assignments={assignments}
            setAssignments={setAssignments}
            quizzes={quizzes}
            groups={groups}
          />
        )}
      </div>
    </div>
  );
}

function QuizzesTab({ quizzes, onReload }: { quizzes: QuizSummary[]; onReload: () => void }) {
  const handleImport = async () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.md,.quiz.md';
    input.onchange = async () => {
      const file = input.files?.[0];
      if (!file) return;
      try {
        await quizApi.importFile(file);
        onReload();
      } catch (err: unknown) {
        alert(getApiErrorDetail(err) || 'Ошибка импорта');
      }
    };
    input.click();
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Удалить тест?')) return;
    await quizApi.remove(id);
    onReload();
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-lg font-semibold text-gray-700 dark:text-gray-200">Тесты</h2>
        <button onClick={handleImport} className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 transition">
          Импортировать .quiz.md
        </button>
      </div>
      {quizzes.length === 0 ? (
        <p className="text-gray-500 dark:text-gray-400">Нет тестов. Импортируйте .quiz.md файл.</p>
      ) : (
        <div className="space-y-3">
          {quizzes.map((q) => (
            <div key={q.id} className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 p-5 shadow-sm flex justify-between items-center">
              <div>
                <h3 className="font-semibold text-gray-800 dark:text-gray-100">
                  <LatexText text={q.title} className="inline" />
                </h3>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                  {q.question_count} вопросов · {q.time_limit_minutes ? `${q.time_limit_minutes} мин` : 'без лимита'}
                </p>
              </div>
              <div className="flex gap-2">
                <Link
                  to={`/teacher/quiz/${q.id}`}
                  className="text-blue-600 dark:text-blue-400 text-sm hover:underline"
                >
                  Подробнее
                </Link>
                <button onClick={() => handleDelete(q.id)} className="text-red-500 text-sm hover:underline">
                  Удалить
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function GroupsTab({ groups, onReload }: { groups: GroupOut[]; onReload: () => void }) {
  const [newName, setNewName] = useState('');
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) return;
    setCreating(true);
    setError('');
    try {
      await groupApi.create(newName.trim());
      setNewName('');
      onReload();
    } catch (err: unknown) {
      setError(getApiErrorDetail(err) || 'Ошибка при создании группы');
    }
    setCreating(false);
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Удалить группу и всех учеников в ней?')) return;
    try {
      await groupApi.remove(id);
      onReload();
    } catch (err: unknown) {
      setError(getApiErrorDetail(err) || 'Ошибка при удалении');
    }
  };

  return (
    <div>
      <h2 className="text-lg font-semibold text-gray-700 dark:text-gray-200 mb-4">Группы</h2>
      {error && (
        <div className="mb-4 p-3 rounded-lg bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 text-sm">
          {error}
        </div>
      )}
      <form onSubmit={handleCreate} className="flex gap-2 mb-4">
        <input
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          placeholder="Название группы..."
          className="flex-1 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <button
          type="submit"
          disabled={creating || !newName.trim()}
          className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition"
        >
          {creating ? 'Создание...' : 'Создать'}
        </button>
      </form>
      <div className="space-y-3">
        {groups.map((g) => (
          <div key={g.id} className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 p-5 shadow-sm flex justify-between items-center">
            <div>
              <h3 className="font-semibold text-gray-800 dark:text-gray-100">{g.name}</h3>
              <p className="text-sm text-gray-500 dark:text-gray-400">{g.student_count} учеников</p>
            </div>
            <div className="flex gap-2">
              <Link to={`/teacher/group/${g.id}`} className="text-blue-600 dark:text-blue-400 text-sm hover:underline">Ученики</Link>
              <button onClick={() => handleDelete(g.id)} className="text-red-500 text-sm hover:underline">Удалить</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function AssignmentsTab({
  assignments, setAssignments, quizzes, groups,
}: {
  assignments: AssignmentOut[];
  setAssignments: React.Dispatch<React.SetStateAction<AssignmentOut[]>>;
  quizzes: QuizSummary[];
  groups: GroupOut[];
}) {
  const [quizId, setQuizId] = useState<number | ''>('');
  const [groupId, setGroupId] = useState<number | ''>('');
  const [startsAt, setStartsAt] = useState('');
  const [durationInput, setDurationInput] = useState('45');
  const [startWindowInput, setStartWindowInput] = useState('45');
  // Tracks whether the teacher has manually touched the start-window field —
  // until then we mirror the duration value so the common case (one number)
  // stays one number.
  const [startWindowTouched, setStartWindowTouched] = useState(false);
  // shared_deadline=true → every attempt's deadline is anchored to
  // starts_at + duration. Late starters get less time. The start-window field
  // is hidden in this mode (the server forces it = duration anyway).
  const [sharedDeadline, setSharedDeadline] = useState(false);
  const [formError, setFormError] = useState('');
  const [copied, setCopied] = useState<number | null>(null);
  const [editingDuration, setEditingDuration] = useState<number | null>(null);
  const [editDurationValue, setEditDurationValue] = useState('');
  const [editingStartWindow, setEditingStartWindow] = useState<number | null>(null);
  const [editStartWindowValue, setEditStartWindowValue] = useState('');
  const [editingStart, setEditingStart] = useState<number | null>(null);
  const [editStartValue, setEditStartValue] = useState('');
  // When non-null, a teacher is being asked to choose between Reset / Keep
  // for this many in-progress attempts before we change starts_at.
  const [pendingStartChange, setPendingStartChange] = useState<{
    assignmentId: number;
    iso: string;
    inProgressAttempts: number;
  } | null>(null);

  const parsePositiveInt = (value: string): number | null => {
    if (!/^\d+$/.test(value.trim())) return null;
    const n = Number(value);
    if (!Number.isInteger(n) || n <= 0) return null;
    return n;
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError('');
    const duration = parsePositiveInt(durationInput);
    // In shared-deadline mode the start window is implicitly = duration;
    // we don't even bother sending the field. Otherwise: if the teacher
    // never touched it, mirror the duration (one-knob behavior).
    const startWindow = sharedDeadline
      ? duration
      : parsePositiveInt(startWindowTouched ? startWindowInput : durationInput);
    if (!quizId || !groupId || !startsAt || !duration || !startWindow) {
      setFormError('Введите положительные целые числа для окна запуска и длительности попытки.');
      return;
    }
    const { data } = await assignmentApi.create({
      quiz_id: Number(quizId),
      group_id: Number(groupId),
      starts_at: new Date(startsAt).toISOString(),
      duration_minutes: duration,
      shared_deadline: sharedDeadline,
      ...(sharedDeadline ? {} : { start_window_minutes: startWindow }),
    });
    setAssignments((prev) => [data, ...prev]);
  };

  const toggleSharedDeadline = async (a: AssignmentOut) => {
    const next = !a.shared_deadline;
    setAssignments((prev) => prev.map((x) => (
      x.id === a.id
        ? {
            ...x,
            shared_deadline: next,
            start_window_minutes: next ? x.duration_minutes : x.start_window_minutes,
            ends_at: next
              ? new Date(new Date(x.starts_at).getTime() + x.duration_minutes * 60_000).toISOString()
              : x.ends_at,
          }
        : x
    )));
    try {
      const { data } = await assignmentApi.update(a.id, { shared_deadline: next });
      setAssignments((prev) => prev.map((x) => (x.id === a.id ? data : x)));
    } catch {
      setAssignments((prev) => prev.map((x) => (x.id === a.id ? a : x)));
    }
  };

  const modeLabel = (mode: StudentViewMode) => {
    if (mode === 'closed') return 'Скрыто';
    if (mode === 'attempt') return 'Показывать попытку';
    return 'Показывать результаты';
  };

  const modeClasses = (mode: StudentViewMode) => {
    if (mode === 'closed') return 'bg-gray-200 text-gray-600 dark:bg-gray-700 dark:text-gray-300';
    if (mode === 'attempt') return 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300';
    return 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300';
  };

  const nextMode = (mode: StudentViewMode): StudentViewMode => {
    if (mode === 'closed') return 'attempt';
    if (mode === 'attempt') return 'results';
    return 'closed';
  };

  const cycleStudentViewMode = async (a: AssignmentOut) => {
    const next = nextMode(a.student_view_mode);
    setAssignments((prev) => prev.map((x) => (
      x.id === a.id ? { ...x, student_view_mode: next, results_visible: next === 'results' } : x
    )));
    try {
      await assignmentApi.update(a.id, { student_view_mode: next });
    } catch {
      // Roll back optimistic change on failure.
      setAssignments((prev) => prev.map((x) => (
        x.id === a.id ? { ...x, student_view_mode: a.student_view_mode, results_visible: a.student_view_mode === 'results' } : x
      )));
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Удалить назначение?')) return;
    setAssignments((prev) => prev.filter((a) => a.id !== id));
    await assignmentApi.remove(id);
  };

  const copyLink = (a: AssignmentOut) => {
    const url = `${window.location.origin}/quiz/${a.share_code}`;
    navigator.clipboard.writeText(url);
    setCopied(a.id);
    setTimeout(() => setCopied(null), 2000);
  };

  const startEditDuration = (a: AssignmentOut) => {
    setEditingDuration(a.id);
    setEditDurationValue(String(a.duration_minutes));
  };

  const saveDuration = async (id: number) => {
    const parsed = parsePositiveInt(editDurationValue);
    if (!parsed) {
      alert('Длительность должна быть положительным целым числом.');
      return;
    }
    const { data } = await assignmentApi.update(id, { duration_minutes: parsed });
    setAssignments((prev) => prev.map((a) => (a.id === id ? data : a)));
    setEditingDuration(null);
  };

  const startEditStartWindow = (a: AssignmentOut) => {
    setEditingStartWindow(a.id);
    setEditStartWindowValue(String(a.start_window_minutes));
  };

  const saveStartWindow = async (id: number) => {
    const parsed = parsePositiveInt(editStartWindowValue);
    if (!parsed) {
      alert('Окно запуска должно быть положительным целым числом.');
      return;
    }
    const { data } = await assignmentApi.update(id, { start_window_minutes: parsed });
    setAssignments((prev) => prev.map((a) => (a.id === id ? data : a)));
    setEditingStartWindow(null);
  };

  const toDateTimeLocal = (iso: string) => {
    const d = new Date(iso);
    const local = new Date(d.getTime() - d.getTimezoneOffset() * 60000);
    return local.toISOString().slice(0, 16);
  };

  const startEditStart = (a: AssignmentOut) => {
    setEditingStart(a.id);
    setEditStartValue(toDateTimeLocal(a.starts_at));
  };

  // Submit the starts_at change. When there are no in-progress attempts the
  // server doesn't need (and ignores) on_open_attempts, so we don't ask. When
  // there are, we open the explicit reset/keep modal — the destructive cascade
  // is intentional but must never happen by accident.
  const saveStart = (a: AssignmentOut) => {
    if (!editStartValue) return;
    const iso = new Date(editStartValue).toISOString();
    if (a.in_progress_attempts > 0) {
      setPendingStartChange({
        assignmentId: a.id,
        iso,
        inProgressAttempts: a.in_progress_attempts,
      });
      return;
    }
    void commitStartChange(a.id, iso, undefined);
  };

  const commitStartChange = async (
    id: number,
    iso: string,
    onOpenAttempts: 'reset' | 'keep' | undefined,
  ) => {
    try {
      const { data } = await assignmentApi.update(id, {
        starts_at: iso,
        ...(onOpenAttempts ? { on_open_attempts: onOpenAttempts } : {}),
      });
      setAssignments((prev) => prev.map((a) => (a.id === id ? data : a)));
      setEditingStart(null);
      setPendingStartChange(null);
    } catch (err: unknown) {
      alert(getApiErrorDetail(err) || 'Ошибка при сохранении времени старта.');
    }
  };

  const inp = "border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded-lg px-3 py-2 text-sm";

  return (
    <div>
      <h2 className="text-lg font-semibold text-gray-700 dark:text-gray-200 mb-4">Назначения</h2>
      <form onSubmit={handleCreate} className="grid grid-cols-2 gap-3 mb-6 bg-white dark:bg-gray-800 p-4 rounded-xl border border-gray-200 dark:border-gray-700">
        <SearchSelect
          options={quizzes.map((q) => ({ value: q.id, label: q.title }))}
          value={quizId}
          onChange={(v) => setQuizId(v)}
          placeholder="Поиск теста..."
        />
        <SearchSelect
          options={groups.map((g) => ({ value: g.id, label: g.name }))}
          value={groupId}
          onChange={(v) => setGroupId(v)}
          placeholder="Поиск группы..."
        />
        <input type="datetime-local" value={startsAt} onChange={(e) => setStartsAt(e.target.value)} className={inp} />
        <div />
        <div
          role="radiogroup"
          aria-label="Режим дедлайна"
          className="col-span-2 flex flex-col sm:flex-row gap-2 items-stretch sm:items-center bg-gray-100 dark:bg-gray-700 rounded-lg p-1"
        >
          <button
            type="button"
            role="radio"
            aria-checked={!sharedDeadline}
            onClick={() => setSharedDeadline(false)}
            className={`flex-1 px-3 py-1.5 text-xs sm:text-sm rounded-md transition text-left sm:text-center ${
              !sharedDeadline
                ? 'bg-white dark:bg-gray-900 shadow text-gray-800 dark:text-gray-100'
                : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
            }`}
            title="У каждого ученика свой таймер от момента, когда он нажал Начать."
          >
            Индивидуальный таймер
          </button>
          <button
            type="button"
            role="radio"
            aria-checked={sharedDeadline}
            onClick={() => setSharedDeadline(true)}
            className={`flex-1 px-3 py-1.5 text-xs sm:text-sm rounded-md transition text-left sm:text-center ${
              sharedDeadline
                ? 'bg-white dark:bg-gray-900 shadow text-gray-800 dark:text-gray-100'
                : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
            }`}
            title="Все заканчивают в одно и то же время. Кто начал позже — успеет меньше."
          >
            Единый дедлайн
          </button>
        </div>
        <div className="flex items-center gap-2">
          <label htmlFor="create-duration" className="text-xs text-gray-500 dark:text-gray-400">
            Длительность попытки
          </label>
          <input
            id="create-duration"
            type="text"
            inputMode="numeric"
            value={durationInput}
            onChange={(e) => setDurationInput(e.target.value)}
            className={`w-20 ${inp}`}
            placeholder="45"
          />
          <span className="text-xs text-gray-500 dark:text-gray-400">мин</span>
        </div>
        {sharedDeadline ? (
          <div className="flex items-center text-xs text-gray-500 dark:text-gray-400">
            Окно запуска = длительности попытки. Все заканчивают одновременно.
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <label htmlFor="create-start-window" className="text-xs text-gray-500 dark:text-gray-400">
              Окно запуска
            </label>
            <input
              id="create-start-window"
              type="text"
              inputMode="numeric"
              value={startWindowTouched ? startWindowInput : durationInput}
              onChange={(e) => {
                setStartWindowTouched(true);
                setStartWindowInput(e.target.value);
              }}
              className={`w-20 ${inp}`}
              placeholder="45"
              title="Сколько минут после старта ученики могут начать попытку. По умолчанию равно длительности попытки."
            />
            <span className="text-xs text-gray-500 dark:text-gray-400">мин</span>
          </div>
        )}
        {formError && (
          <div className="col-span-2 text-xs text-red-600 dark:text-red-400">{formError}</div>
        )}
        <button type="submit" className="col-span-2 bg-blue-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-blue-700 transition">
          Назначить
        </button>
      </form>

      <div className="space-y-3">
        {assignments.map((a) => (
          <div key={a.id} className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5 shadow-sm">
            <div className="flex justify-between items-start">
              <div>
                <h3 className="font-semibold text-gray-800 dark:text-gray-100">
                  <LatexText text={a.quiz_title} className="inline" />
                </h3>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                  {a.group_name} · {new Date(a.starts_at).toLocaleString('ru')}
                </p>
                <div className="flex items-center gap-2 mt-1">
                  {editingStart === a.id ? (
                    <>
                      <span className="text-xs text-gray-500 dark:text-gray-400">Старт:</span>
                      <input
                        type="datetime-local"
                        value={editStartValue}
                        onChange={(e) => setEditStartValue(e.target.value)}
                        className="border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded px-2 py-0.5 text-xs"
                      />
                      <button onClick={() => saveStart(a)} className="text-xs text-green-600 dark:text-green-400 hover:underline">Сохранить</button>
                      <button onClick={() => setEditingStart(null)} className="text-xs text-gray-500 dark:text-gray-400 hover:underline">Отмена</button>
                    </>
                  ) : (
                    <>
                      <span className="text-xs text-gray-500 dark:text-gray-400">
                        Старт: {new Date(a.starts_at).toLocaleString('ru')}
                      </span>
                      <button onClick={() => startEditStart(a)} className="text-xs text-blue-600 dark:text-blue-400 hover:underline">Изменить</button>
                    </>
                  )}
                </div>
                <div className="flex items-center gap-2 mt-1">
                  {editingDuration === a.id ? (
                    <>
                      <span className="text-xs text-gray-500 dark:text-gray-400">Длительность попытки:</span>
                      <input
                        type="text"
                        inputMode="numeric"
                        value={editDurationValue}
                        onChange={(e) => setEditDurationValue(e.target.value)}
                        className="w-16 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded px-2 py-0.5 text-xs"
                      />
                      <span className="text-xs text-gray-500 dark:text-gray-400">мин</span>
                      <button onClick={() => saveDuration(a.id)} className="text-xs text-green-600 dark:text-green-400 hover:underline">Сохранить</button>
                      <button onClick={() => setEditingDuration(null)} className="text-xs text-gray-500 dark:text-gray-400 hover:underline">Отмена</button>
                    </>
                  ) : (
                    <>
                      <span className="text-xs text-gray-500 dark:text-gray-400">
                        Длительность попытки: {a.duration_minutes} мин
                      </span>
                      <button onClick={() => startEditDuration(a)} className="text-xs text-blue-600 dark:text-blue-400 hover:underline">Изменить</button>
                    </>
                  )}
                  {a.in_progress_attempts > 0 && (
                    <span className="text-xs text-amber-600 dark:text-amber-400">
                      · {a.in_progress_attempts} активных попыток
                    </span>
                  )}
                </div>
                {a.shared_deadline ? (
                  <div className="flex items-center gap-2 mt-1">
                    <span
                      className="text-xs text-gray-500 dark:text-gray-400"
                      title="В режиме «Единый дедлайн» окно запуска совпадает с длительностью."
                    >
                      Дедлайн для всех: {new Date(a.ends_at).toLocaleString('ru')}
                    </span>
                  </div>
                ) : (
                  <div className="flex items-center gap-2 mt-1">
                    {editingStartWindow === a.id ? (
                      <>
                        <span className="text-xs text-gray-500 dark:text-gray-400">Окно запуска:</span>
                        <input
                          type="text"
                          inputMode="numeric"
                          value={editStartWindowValue}
                          onChange={(e) => setEditStartWindowValue(e.target.value)}
                          className="w-16 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded px-2 py-0.5 text-xs"
                        />
                        <span className="text-xs text-gray-500 dark:text-gray-400">мин</span>
                        <button onClick={() => saveStartWindow(a.id)} className="text-xs text-green-600 dark:text-green-400 hover:underline">Сохранить</button>
                        <button onClick={() => setEditingStartWindow(null)} className="text-xs text-gray-500 dark:text-gray-400 hover:underline">Отмена</button>
                      </>
                    ) : (
                      <>
                        <span
                          className="text-xs text-gray-500 dark:text-gray-400"
                          title="Сколько минут после старта ученики могут начать попытку"
                        >
                          Окно запуска: {a.start_window_minutes} мин
                        </span>
                        <button onClick={() => startEditStartWindow(a)} className="text-xs text-blue-600 dark:text-blue-400 hover:underline">Изменить</button>
                      </>
                    )}
                  </div>
                )}
              </div>
              <div className="flex gap-2 items-center flex-wrap justify-end">
                <button
                  onClick={() => copyLink(a)}
                  className="text-xs px-3 py-1 rounded-full font-medium bg-indigo-100 text-indigo-700 dark:bg-indigo-900 dark:text-indigo-300 transition"
                >
                  {copied === a.id ? 'Скопировано!' : 'Ссылка'}
                </button>
                <button
                  onClick={() => void toggleSharedDeadline(a)}
                  title={
                    a.shared_deadline
                      ? 'Все заканчивают одновременно (starts_at + длительность). Кто начал позже — успеет меньше. Нажмите, чтобы переключить.'
                      : 'У каждого свой таймер от момента, когда он нажал Начать. Нажмите, чтобы переключить.'
                  }
                  className={`text-xs px-3 py-1 rounded-full font-medium transition ${
                    a.shared_deadline
                      ? 'bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300'
                      : 'bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-300'
                  }`}
                >
                  {a.shared_deadline ? 'Единый дедлайн' : 'Индивидуальный таймер'}
                </button>
                <button
                  onClick={() => cycleStudentViewMode(a)}
                  className={`text-xs px-3 py-1 rounded-full font-medium transition ${modeClasses(a.student_view_mode)}`}
                >
                  {modeLabel(a.student_view_mode)}
                </button>
                <Link
                  to={`/teacher/assignment/${a.id}/results`}
                  className="text-blue-600 dark:text-blue-400 text-sm hover:underline"
                >
                  Результаты
                </Link>
                <button
                  onClick={() => handleDelete(a.id)}
                  className="text-red-500 dark:text-red-400 text-sm hover:underline"
                >
                  Удалить
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {pendingStartChange && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="start-change-title"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4"
        >
          <div className="w-full max-w-md bg-white dark:bg-gray-900 rounded-2xl shadow-xl p-6">
            <h3 id="start-change-title" className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">
              Что делать с активными попытками?
            </h3>
            <p className="text-sm text-gray-600 dark:text-gray-300 mb-1">
              {pendingStartChange.inProgressAttempts === 1
                ? 'Сейчас идёт 1 активная попытка.'
                : `Сейчас идёт ${pendingStartChange.inProgressAttempts} активных попыток.`}
            </p>
            <p className="text-sm text-gray-600 dark:text-gray-300 mb-5">
              <strong>Сбросить</strong> — удалит все незавершённые попытки (полный перезапуск теста).
              Действие необратимо.
              <br />
              <strong>Сохранить</strong> — попытки продолжатся со своим текущим таймером;
              изменится только время старта для тех, кто ещё не начал.
            </p>
            <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2">
              <button
                onClick={() => setPendingStartChange(null)}
                className="px-4 py-2 rounded-lg text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition"
              >
                Отмена
              </button>
              <button
                onClick={() =>
                  void commitStartChange(
                    pendingStartChange.assignmentId,
                    pendingStartChange.iso,
                    'keep',
                  )
                }
                className="px-4 py-2 rounded-lg text-sm font-medium bg-blue-600 text-white hover:bg-blue-700 transition"
              >
                Сохранить попытки
              </button>
              <button
                onClick={() =>
                  void commitStartChange(
                    pendingStartChange.assignmentId,
                    pendingStartChange.iso,
                    'reset',
                  )
                }
                className="px-4 py-2 rounded-lg text-sm font-medium bg-red-600 text-white hover:bg-red-700 transition"
              >
                Сбросить попытки и перезапустить
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
