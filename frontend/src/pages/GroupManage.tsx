import { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { groupApi } from '../api/endpoints';
import type { StudentOut, GroupOut } from '../types/quiz';
import ThemeToggle from '../components/ThemeToggle';

function getApiErrorDetail(err: unknown): string | undefined {
  if (typeof err === 'object' && err !== null && 'response' in err) {
    const detail = (err as { response?: { data?: { detail?: unknown } } }).response?.data?.detail;
    if (typeof detail === 'string') return detail;
  }
  return undefined;
}

export default function GroupManage() {
  const { groupId } = useParams<{ groupId: string }>();
  const navigate = useNavigate();
  const [group, setGroup] = useState<GroupOut | null>(null);
  const [students, setStudents] = useState<StudentOut[]>([]);
  const [bulkText, setBulkText] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);
  const [editingNameId, setEditingNameId] = useState<number | null>(null);
  const [editingNameValue, setEditingNameValue] = useState('');
  const [editingPasswordId, setEditingPasswordId] = useState<number | null>(null);
  const [editingPasswordValue, setEditingPasswordValue] = useState('');
  const [savingStudentId, setSavingStudentId] = useState<number | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = () => {
    if (!groupId) return;
    groupApi.get(Number(groupId)).then((r) => setGroup(r.data)).catch(() => {});
    groupApi.students(Number(groupId)).then((r) => setStudents(r.data));
  };
  useEffect(load, [groupId]);

  const flash = (msg: string) => {
    setSuccess(msg);
    setTimeout(() => setSuccess(''), 3000);
  };

  const parseCSV = (text: string) => {
    return text.trim().split('\n').filter(Boolean).map((line) => {
      const parts = line.split(',').map((s) => s.trim());
      return {
        username: parts[0],
        password: parts[1] || 'quiz2026',
        display_name: parts[2] || parts[0],
      };
    });
  };

  const handleBulkAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (!bulkText.trim()) return;
    const parsed = parseCSV(bulkText);
    if (parsed.length === 0) return;
    setLoading(true);
    try {
      const { data } = await groupApi.addStudents(Number(groupId), parsed);
      setBulkText('');
      flash(`Добавлено ${data.length} учеников`);
      load();
    } catch (err: unknown) {
      setError(getApiErrorDetail(err) || 'Ошибка при добавлении');
    }
    setLoading(false);
  };

  const handleFileImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setError('');
    const text = await file.text();
    const parsed = parseCSV(text);
    if (parsed.length === 0) {
      setError('Файл пустой или в неверном формате');
      return;
    }
    setLoading(true);
    try {
      const { data } = await groupApi.addStudents(Number(groupId), parsed);
      flash(`Импортировано ${data.length} учеников из ${file.name}`);
      load();
    } catch (err: unknown) {
      setError(getApiErrorDetail(err) || 'Ошибка при импорте');
    }
    setLoading(false);
    if (fileRef.current) fileRef.current.value = '';
  };

  const handleDelete = async (s: StudentOut) => {
    if (!confirm(`Удалить ученика ${s.display_name} (${s.username})?`)) return;
    try {
      await groupApi.removeStudent(Number(groupId), s.id);
      load();
    } catch (err: unknown) {
      setError(getApiErrorDetail(err) || 'Ошибка при удалении');
    }
  };

  const startEditName = (s: StudentOut) => {
    setEditingNameId(s.id);
    setEditingNameValue(s.display_name);
  };

  const saveName = async (studentId: number) => {
    const value = editingNameValue.trim();
    if (!value) {
      setError('Имя не может быть пустым');
      return;
    }
    setSavingStudentId(studentId);
    setError('');
    try {
      await groupApi.updateStudent(Number(groupId), studentId, { display_name: value });
      setEditingNameId(null);
      setEditingNameValue('');
      flash('Имя ученика обновлено');
      load();
    } catch (err: unknown) {
      setError(getApiErrorDetail(err) || 'Ошибка при обновлении имени');
    } finally {
      setSavingStudentId(null);
    }
  };

  const startEditPassword = (s: StudentOut) => {
    setEditingPasswordId(s.id);
    setEditingPasswordValue('');
  };

  const savePassword = async (studentId: number) => {
    if (!editingPasswordValue) {
      setError('Пароль не может быть пустым');
      return;
    }
    setSavingStudentId(studentId);
    setError('');
    try {
      await groupApi.updateStudent(Number(groupId), studentId, { password: editingPasswordValue });
      setEditingPasswordId(null);
      setEditingPasswordValue('');
      flash('Пароль ученика обновлён');
    } catch (err: unknown) {
      setError(getApiErrorDetail(err) || 'Ошибка при обновлении пароля');
    } finally {
      setSavingStudentId(null);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950">
      <header className="bg-white dark:bg-gray-900 shadow-sm border-b border-gray-200 dark:border-gray-700">
        <div className="max-w-4xl mx-auto px-4 py-4 flex justify-between items-center">
          <div>
            <h1 className="text-xl font-bold text-gray-800 dark:text-gray-100">
              {group ? group.name : 'Группа'}
            </h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">{students.length} учеников</p>
          </div>
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <button onClick={() => navigate(-1)} className="text-sm text-gray-500 dark:text-gray-400 hover:text-blue-600 transition">Назад</button>
          </div>
        </div>
      </header>
      <main className="max-w-4xl mx-auto px-4 py-6">
        {success && (
          <div className="mb-4 p-3 rounded-lg bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 text-sm">
            {success}
          </div>
        )}
        {error && (
          <div className="mb-4 p-3 rounded-lg bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 text-sm">
            {error}
          </div>
        )}

        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 p-5 mb-6">
          <h2 className="font-semibold text-gray-700 dark:text-gray-200 mb-3">Добавить учеников</h2>
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">
            Формат CSV: <code className="bg-gray-100 dark:bg-gray-800 px-1 rounded">логин, пароль, имя</code> (по одному на строку). Пароль и имя — опционально (по умолчанию quiz2026 и логин).
          </p>

          <div className="flex gap-2 mb-3">
            <button
              onClick={() => fileRef.current?.click()}
              disabled={loading}
              className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition"
            >
              Импорт из файла (.csv, .txt)
            </button>
            <input
              ref={fileRef}
              type="file"
              accept=".csv,.txt"
              onChange={handleFileImport}
              className="hidden"
            />
          </div>

          <form onSubmit={handleBulkAdd} className="space-y-3">
            <textarea
              value={bulkText}
              onChange={(e) => setBulkText(e.target.value)}
              rows={5}
              placeholder={"student01, quiz2026, Иванов Иван\nstudent02, quiz2026, Петров Пётр\nstudent03"}
              className="w-full border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              type="submit"
              disabled={loading || !bulkText.trim()}
              className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition"
            >
              {loading ? 'Добавление...' : 'Добавить'}
            </button>
          </form>
        </div>

        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800">
              <tr className="text-left text-gray-500 dark:text-gray-400">
                <th className="px-5 py-3">Логин</th>
                <th className="px-5 py-3">Имя</th>
                <th className="px-5 py-3 w-72"></th>
              </tr>
            </thead>
            <tbody>
              {students.map((s) => (
                <tr key={s.id} className="border-b border-gray-100 dark:border-gray-800 last:border-0">
                  <td className="px-5 py-3 font-mono text-gray-700 dark:text-gray-200">{s.username}</td>
                  <td className="px-5 py-3 text-gray-800 dark:text-gray-100">
                    {editingNameId === s.id ? (
                      <div className="flex items-center gap-2">
                        <input
                          value={editingNameValue}
                          onChange={(e) => setEditingNameValue(e.target.value)}
                          className="border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded px-2 py-1 text-xs w-44"
                        />
                        <button
                          onClick={() => saveName(s.id)}
                          disabled={savingStudentId === s.id}
                          className="text-green-600 dark:text-green-400 text-xs hover:underline disabled:opacity-50"
                        >
                          Сохранить
                        </button>
                        <button
                          onClick={() => setEditingNameId(null)}
                          className="text-gray-500 dark:text-gray-400 text-xs hover:underline"
                        >
                          Отмена
                        </button>
                      </div>
                    ) : (
                      s.display_name
                    )}
                  </td>
                  <td className="px-5 py-3 text-right">
                    <div className="flex flex-col items-end gap-1">
                      <div className="flex gap-3">
                        <button
                          onClick={() => startEditName(s)}
                          className="text-blue-600 dark:text-blue-400 text-xs hover:underline"
                        >
                          Изменить имя
                        </button>
                        <button
                          onClick={() => startEditPassword(s)}
                          className="text-indigo-600 dark:text-indigo-400 text-xs hover:underline"
                        >
                          Сменить пароль
                        </button>
                        <button
                          onClick={() => handleDelete(s)}
                          className="text-red-500 dark:text-red-400 text-xs hover:underline"
                        >
                          Удалить
                        </button>
                      </div>
                      {editingPasswordId === s.id && (
                        <div className="flex items-center gap-2">
                          <input
                            type="text"
                            value={editingPasswordValue}
                            onChange={(e) => setEditingPasswordValue(e.target.value)}
                            placeholder="Новый пароль"
                            className="border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded px-2 py-1 text-xs w-36"
                          />
                          <button
                            onClick={() => savePassword(s.id)}
                            disabled={savingStudentId === s.id}
                            className="text-green-600 dark:text-green-400 text-xs hover:underline disabled:opacity-50"
                          >
                            Сохранить
                          </button>
                          <button
                            onClick={() => setEditingPasswordId(null)}
                            className="text-gray-500 dark:text-gray-400 text-xs hover:underline"
                          >
                            Отмена
                          </button>
                        </div>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
              {students.length === 0 && (
                <tr><td colSpan={3} className="px-5 py-8 text-center text-gray-400 dark:text-gray-500">Нет учеников</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  );
}
