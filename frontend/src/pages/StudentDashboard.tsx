import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { studentApi } from '../api/endpoints';
import type { StudentAssignment } from '../types/quiz';
import { useAuth } from '../hooks/useAuth';
import ThemeToggle from '../components/ThemeToggle';

export default function StudentDashboard() {
  const [assignments, setAssignments] = useState<StudentAssignment[]>([]);
  const [loading, setLoading] = useState(true);
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    studentApi.myAssignments().then((r) => { setAssignments(r.data); setLoading(false); });
  }, []);

  const statusLabel = (s: string) => {
    if (s === 'upcoming') return { text: 'Ожидается', color: 'bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-200' };
    if (s === 'active') return { text: 'Доступен', color: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300' };
    return { text: 'Завершён', color: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300' };
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950">
      <header className="bg-white dark:bg-gray-900 shadow-sm border-b border-gray-200 dark:border-gray-700">
        <div className="max-w-4xl mx-auto px-4 py-4 flex justify-between items-center">
          <div>
            <h1 className="text-xl font-bold text-gray-800 dark:text-gray-100">Мои тесты</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">{user?.display_name}</p>
          </div>
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <button onClick={logout} className="text-sm text-gray-500 hover:text-red-500 dark:text-gray-400 dark:hover:text-red-400 transition">Выйти</button>
          </div>
        </div>
      </header>
      <main className="max-w-4xl mx-auto px-4 py-6">
        {loading ? (
          <p className="text-gray-500 dark:text-gray-400">Загрузка...</p>
        ) : assignments.length === 0 ? (
          <p className="text-gray-500 dark:text-gray-400">Нет доступных тестов.</p>
        ) : (
          <div className="space-y-3">
            {assignments.map((a) => {
              const st = statusLabel(a.status);
              return (
                <div
                  key={a.assignment_id}
                  className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 p-5 flex justify-between items-center shadow-sm"
                >
                  <div>
                    <h2 className="font-semibold text-gray-800 dark:text-gray-100">{a.quiz_title}</h2>
                    <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                      {a.time_limit_minutes ? `${a.time_limit_minutes} мин` : 'Без ограничения'}{' · '}
                      до {new Date(a.ends_at).toLocaleString('ru')}
                    </p>
                    <span className={`inline-block mt-2 text-xs font-medium px-2.5 py-0.5 rounded-full ${st.color}`}>
                      {st.text}
                    </span>
                  </div>
                  <div className="flex gap-2">
                    {a.status === 'active' && (
                      <button
                        onClick={() => navigate(`/student/quiz/${a.assignment_id}`)}
                        className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600 transition"
                      >
                        {a.attempt_id ? 'Продолжить' : 'Начать'}
                      </button>
                    )}
                    {a.status === 'completed' && a.results_visible && a.attempt_id && (
                      <button
                        onClick={() => navigate(`/student/results/${a.attempt_id}`)}
                        className="bg-gray-100 text-gray-700 px-4 py-2 rounded-lg text-sm font-medium hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-200 dark:hover:bg-gray-700 transition"
                      >
                        Результаты
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
