import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { assignmentApi } from '../api/endpoints';
import type { AssignmentResultsSummary } from '../types/quiz';
import ThemeToggle from '../components/ThemeToggle';
import LatexText from '../components/LatexText';

function getErrorDetail(err: unknown): string | undefined {
  if (typeof err === 'object' && err !== null && 'response' in err) {
    const detail = (err as { response?: { data?: { detail?: unknown } } }).response?.data?.detail;
    if (typeof detail === 'string') return detail;
  }
  return undefined;
}

function extractFilename(disposition: string | undefined, fallback: string): string {
  if (!disposition) return fallback;
  const match = disposition.match(/filename="?([^"]+)"?/i);
  return match?.[1] ?? fallback;
}

export default function AssignmentResults() {
  const { assignmentId } = useParams<{ assignmentId: string }>();
  const navigate = useNavigate();
  const [data, setData] = useState<AssignmentResultsSummary | null>(null);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState('');

  useEffect(() => {
    if (!assignmentId) return;
    assignmentApi.results(Number(assignmentId)).then((r) => setData(r.data));
  }, [assignmentId]);

  if (!data) {
    return <div className="min-h-screen flex items-center justify-center"><p className="text-gray-500 dark:text-gray-400">Загрузка...</p></div>;
  }

  const sorted = [...data.results].sort((a, b) => (b.score ?? 0) - (a.score ?? 0));

  const handleExport = async () => {
    if (!assignmentId || exporting) return;
    setExportError('');
    setExporting(true);
    try {
      const resp = await assignmentApi.exportResultsCsv(Number(assignmentId));
      const fallback = `assignment_${assignmentId}_results.csv`;
      const contentDisposition = resp.headers['content-disposition'] as string | undefined;
      const filename = extractFilename(contentDisposition, fallback);
      const blob = new Blob([resp.data], { type: 'text/csv;charset=utf-8;' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err: unknown) {
      setExportError(getErrorDetail(err) || 'Не удалось экспортировать CSV');
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950">
      <header className="bg-white dark:bg-gray-900 shadow-sm border-b border-gray-200 dark:border-gray-700">
        <div className="max-w-4xl mx-auto px-4 py-4 flex justify-between items-center">
          <div>
            <h1 className="text-xl font-bold text-gray-800 dark:text-gray-100">
              <LatexText text={data.quiz_title} className="inline" />
            </h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">{data.group_name} · макс. {data.max_score} баллов</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleExport}
              disabled={exporting}
              className="text-sm bg-indigo-600 text-white px-3 py-1.5 rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition"
            >
              {exporting ? 'Экспорт...' : 'Экспорт CSV'}
            </button>
            <ThemeToggle />
            <button onClick={() => navigate('/teacher')} className="text-sm text-gray-500 dark:text-gray-400 hover:text-blue-600 transition">Назад</button>
          </div>
        </div>
      </header>
      <main className="max-w-4xl mx-auto px-4 py-6">
        {exportError && (
          <div className="mb-4 p-3 rounded-lg bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 text-sm">
            {exportError}
          </div>
        )}
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-950">
              <tr className="text-left text-gray-600 dark:text-gray-300">
                <th className="px-5 py-3">#</th>
                <th className="px-5 py-3">Ученик</th>
                <th className="px-5 py-3">Статус</th>
                <th className="px-5 py-3">Баллы</th>
                <th className="px-5 py-3">%</th>
                <th className="px-5 py-3">Отправлено</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((r, i) => {
                const pct = data.max_score > 0 ? Math.round(((r.score ?? 0) / data.max_score) * 100) : 0;
                return (
                  <tr
                    key={r.student_id}
                    onClick={() => navigate(`/teacher/assignment/${assignmentId}/attempts/${r.attempt_id}`)}
                    className="border-b border-gray-100 dark:border-gray-800 last:border-0 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 transition"
                  >
                    <td className="px-5 py-3 text-gray-400 dark:text-gray-500">{i + 1}</td>
                    <td className="px-5 py-3 font-medium text-blue-600 dark:text-blue-400">{r.student_name}</td>
                    <td className="px-5 py-3">
                      <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                        r.status === 'submitted'
                          ? 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300'
                          : 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300'
                      }`}>
                        {r.status === 'submitted' ? 'Сдан' : 'В процессе'}
                      </span>
                    </td>
                    <td className="px-5 py-3">
                      {r.score !== null ? (
                        <span className={`font-semibold ${pct >= 70 ? 'text-green-600 dark:text-green-400' : pct >= 40 ? 'text-amber-600 dark:text-amber-400' : 'text-red-500 dark:text-red-400'}`}>
                          {r.score}/{data.max_score}
                        </span>
                      ) : (
                        <span className="text-gray-400 dark:text-gray-500">—</span>
                      )}
                    </td>
                    <td className="px-5 py-3 text-gray-500 dark:text-gray-400">{r.score !== null ? `${pct}%` : '—'}</td>
                    <td className="px-5 py-3 text-gray-500 dark:text-gray-400 text-xs">
                      {r.submitted_at ? new Date(r.submitted_at).toLocaleString('ru') : '—'}
                    </td>
                  </tr>
                );
              })}
              {sorted.length === 0 && (
                <tr><td colSpan={6} className="px-5 py-8 text-center text-gray-400 dark:text-gray-500">Нет результатов</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  );
}
