import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { quizApi, groupApi, assignmentApi } from '../api/endpoints';
import type { QuizSummary, GroupOut, AssignmentOut } from '../types/quiz';
import { useAuth } from '../hooks/useAuth';
import SearchSelect from '../components/SearchSelect';
import ThemeToggle from '../components/ThemeToggle';

export default function TeacherDashboard() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [quizzes, setQuizzes] = useState<QuizSummary[]>([]);
  const [groups, setGroups] = useState<GroupOut[]>([]);
  const [assignments, setAssignments] = useState<AssignmentOut[]>([]);
  const [tab, setTab] = useState<'quizzes' | 'groups' | 'assignments'>('quizzes');

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
        <div className="flex gap-1 bg-gray-200 dark:bg-gray-700 rounded-lg p-1 mb-6">
          {(['quizzes', 'groups', 'assignments'] as const).map((t) => (
            <button
              key={t}
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
          <QuizzesTab quizzes={quizzes} onReload={reload} navigate={navigate} />
        )}
        {tab === 'groups' && (
          <GroupsTab groups={groups} onReload={reload} navigate={navigate} />
        )}
        {tab === 'assignments' && (
          <AssignmentsTab
            assignments={assignments}
            setAssignments={setAssignments}
            quizzes={quizzes}
            groups={groups}
            navigate={navigate}
          />
        )}
      </div>
    </div>
  );
}

function QuizzesTab({ quizzes, onReload, navigate }: { quizzes: QuizSummary[]; onReload: () => void; navigate: any }) {
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
      } catch (err: any) {
        alert(err.response?.data?.detail || 'Ошибка импорта');
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
                <h3 className="font-semibold text-gray-800 dark:text-gray-100">{q.title}</h3>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                  {q.question_count} вопросов · {q.time_limit_minutes ? `${q.time_limit_minutes} мин` : 'без лимита'}
                </p>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => navigate(`/teacher/quiz/${q.id}`)}
                  className="text-blue-600 dark:text-blue-400 text-sm hover:underline"
                >
                  Подробнее
                </button>
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

function GroupsTab({ groups, onReload, navigate }: { groups: GroupOut[]; onReload: () => void; navigate: any }) {
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
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Ошибка при создании группы');
    }
    setCreating(false);
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Удалить группу и всех учеников в ней?')) return;
    try {
      await groupApi.remove(id);
      onReload();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Ошибка при удалении');
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
              <button onClick={() => navigate(`/teacher/group/${g.id}`)} className="text-blue-600 dark:text-blue-400 text-sm hover:underline">Ученики</button>
              <button onClick={() => handleDelete(g.id)} className="text-red-500 text-sm hover:underline">Удалить</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function AssignmentsTab({
  assignments, setAssignments, quizzes, groups, navigate,
}: {
  assignments: AssignmentOut[];
  setAssignments: React.Dispatch<React.SetStateAction<AssignmentOut[]>>;
  quizzes: QuizSummary[];
  groups: GroupOut[];
  navigate: any;
}) {
  const [quizId, setQuizId] = useState<number | ''>('');
  const [groupId, setGroupId] = useState<number | ''>('');
  const [startsAt, setStartsAt] = useState('');
  const [duration, setDuration] = useState(45);
  const [timeLimit, setTimeLimit] = useState(30);
  const [copied, setCopied] = useState<number | null>(null);
  const [editingTL, setEditingTL] = useState<number | null>(null);
  const [editTLValue, setEditTLValue] = useState(0);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!quizId || !groupId || !startsAt || !duration) return;
    const { data } = await assignmentApi.create({
      quiz_id: Number(quizId),
      group_id: Number(groupId),
      starts_at: new Date(startsAt).toISOString(),
      duration_minutes: duration,
      time_limit_minutes: timeLimit || undefined,
    });
    setAssignments((prev) => [data, ...prev]);
  };

  const toggleResults = async (id: number, visible: boolean) => {
    setAssignments((prev) => prev.map((a) => a.id === id ? { ...a, results_visible: visible } : a));
    await assignmentApi.update(id, { results_visible: visible });
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

  const startEditTL = (a: AssignmentOut) => {
    setEditingTL(a.id);
    setEditTLValue(a.time_limit_minutes ?? 30);
  };

  const saveTL = async (id: number) => {
    setAssignments((prev) => prev.map((a) => a.id === id ? { ...a, time_limit_minutes: editTLValue } : a));
    setEditingTL(null);
    await assignmentApi.update(id, { time_limit_minutes: editTLValue });
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
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500 dark:text-gray-400">Доступен</span>
          <input type="number" min={1} value={duration} onChange={(e) => setDuration(Number(e.target.value))} className={`w-20 ${inp}`} />
          <span className="text-xs text-gray-500 dark:text-gray-400">мин</span>
        </div>
        <div className="flex items-center gap-2 col-span-2">
          <span className="text-xs text-gray-500 dark:text-gray-400">Время на попытку</span>
          <input type="number" min={1} value={timeLimit} onChange={(e) => setTimeLimit(Number(e.target.value))} className={`w-20 ${inp}`} />
          <span className="text-xs text-gray-500 dark:text-gray-400">мин (таймер у ученика)</span>
        </div>
        <button type="submit" className="col-span-2 bg-blue-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-blue-700 transition">
          Назначить
        </button>
      </form>

      <div className="space-y-3">
        {assignments.map((a) => (
          <div key={a.id} className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5 shadow-sm">
            <div className="flex justify-between items-start">
              <div>
                <h3 className="font-semibold text-gray-800 dark:text-gray-100">{a.quiz_title}</h3>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                  {a.group_name} · доступен {a.duration_minutes} мин · {new Date(a.starts_at).toLocaleString('ru')}
                </p>
                <div className="flex items-center gap-2 mt-1">
                  {editingTL === a.id ? (
                    <>
                      <span className="text-xs text-gray-500 dark:text-gray-400">Таймер:</span>
                      <input
                        type="number"
                        min={1}
                        value={editTLValue}
                        onChange={(e) => setEditTLValue(Number(e.target.value))}
                        className="w-16 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded px-2 py-0.5 text-xs"
                      />
                      <span className="text-xs text-gray-500 dark:text-gray-400">мин</span>
                      <button onClick={() => saveTL(a.id)} className="text-xs text-green-600 dark:text-green-400 hover:underline">Сохранить</button>
                      <button onClick={() => setEditingTL(null)} className="text-xs text-gray-500 dark:text-gray-400 hover:underline">Отмена</button>
                    </>
                  ) : (
                    <>
                      <span className="text-xs text-gray-500 dark:text-gray-400">
                        Таймер: {a.time_limit_minutes ? `${a.time_limit_minutes} мин` : 'нет'}
                      </span>
                      <button onClick={() => startEditTL(a)} className="text-xs text-blue-600 dark:text-blue-400 hover:underline">Изменить</button>
                    </>
                  )}
                </div>
              </div>
              <div className="flex gap-2 items-center flex-wrap justify-end">
                <button
                  onClick={() => copyLink(a)}
                  className="text-xs px-3 py-1 rounded-full font-medium bg-indigo-100 text-indigo-700 dark:bg-indigo-900 dark:text-indigo-300 transition"
                >
                  {copied === a.id ? 'Скопировано!' : 'Ссылка'}
                </button>
                <button
                  onClick={() => toggleResults(a.id, !a.results_visible)}
                  className={`text-xs px-3 py-1 rounded-full font-medium transition ${
                    a.results_visible
                      ? 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300'
                      : 'bg-gray-200 text-gray-600 dark:bg-gray-700 dark:text-gray-400'
                  }`}
                >
                  {a.results_visible ? 'Результаты видны' : 'Результаты скрыты'}
                </button>
                <button
                  onClick={() => navigate(`/teacher/assignment/${a.id}/results`)}
                  className="text-blue-600 dark:text-blue-400 text-sm hover:underline"
                >
                  Результаты
                </button>
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
    </div>
  );
}
