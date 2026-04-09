import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { assignmentApi } from '../api/endpoints';
import type { AttemptResult } from '../types/quiz';
import RichText from '../components/RichText';
import LatexText from '../components/LatexText';
import ThemeToggle from '../components/ThemeToggle';

export default function TeacherAttemptDetail() {
  const { assignmentId, attemptId } = useParams<{ assignmentId: string; attemptId: string }>();
  const navigate = useNavigate();
  const [result, setResult] = useState<AttemptResult | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!assignmentId || !attemptId) return;
    assignmentApi.attemptDetail(Number(assignmentId), Number(attemptId))
      .then((r) => setResult(r.data))
      .catch((err) => setError(err.response?.data?.detail || 'Ошибка'));
  }, [assignmentId, attemptId]);

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950">
        <div className="bg-white dark:bg-gray-900 rounded-xl shadow p-8 text-center">
          <p className="text-red-500 mb-4">{error}</p>
          <button onClick={() => navigate(-1)} className="text-blue-600 dark:text-blue-400 hover:underline">Назад</button>
        </div>
      </div>
    );
  }

  if (!result) {
    return <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950"><p className="text-gray-500 dark:text-gray-400">Загрузка...</p></div>;
  }

  const percentage = result.max_score > 0 ? Math.round(((result.score ?? 0) / result.max_score) * 100) : 0;

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950">
      <header className="bg-white dark:bg-gray-900 shadow-sm border-b border-gray-200 dark:border-gray-700">
        <div className="max-w-3xl mx-auto px-4 py-4 flex justify-between items-center">
          <div>
            <h1 className="text-xl font-bold text-gray-800 dark:text-gray-100">{result.student_name}</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {result.submitted_at ? `Отправлено: ${new Date(result.submitted_at).toLocaleString('ru')}` : 'Не отправлено (в процессе)'}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <button onClick={() => navigate(-1)} className="text-sm text-gray-500 dark:text-gray-400 hover:text-blue-600 transition">Назад</button>
          </div>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-6">
        <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6 mb-6 text-center">
          <p className="text-5xl font-bold text-blue-600 dark:text-blue-400">{result.score ?? 0}/{result.max_score}</p>
          <p className="text-gray-500 dark:text-gray-400 mt-1">{percentage}%</p>
        </div>

        {result.questions.map((q, i) => (
          <div
            key={q.question_id}
            className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6 mb-4"
          >
            <div className="flex items-center gap-3 mb-3">
              <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-white text-sm font-bold ${
                q.is_correct ? 'bg-green-500' : q.selected_option_ids || q.text_answer ? 'bg-red-500' : 'bg-gray-400'
              }`}>
                {q.is_correct ? '\u2713' : q.selected_option_ids || q.text_answer ? '\u2717' : '—'}
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="font-semibold text-gray-800 dark:text-gray-100">
                  Вопрос {i + 1}. <LatexText text={q.title} className="inline" />
                </h3>
              </div>
              <div className={`flex-shrink-0 text-sm font-bold px-2.5 py-1 rounded-lg ${
                q.is_correct
                  ? 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300'
                  : 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300'
              }`}>
                {q.points_awarded}/{q.points}
              </div>
            </div>

            {q.body_md && <RichText text={q.body_md} className="text-gray-700 dark:text-gray-200 mb-4 text-sm" />}

            {q.options && q.options.length > 0 && (
              <div className="space-y-2 mb-3">
                {q.options.map((o) => {
                  const selected = q.selected_option_ids?.includes(o.id);
                  const correct = o.is_correct;

                  let border = 'border-gray-200 dark:border-gray-700';
                  let bg = 'bg-white dark:bg-gray-900';
                  if (selected && correct) {
                    border = 'border-green-400 dark:border-green-600';
                    bg = 'bg-green-50 dark:bg-green-900/20';
                  } else if (selected && !correct) {
                    border = 'border-red-400 dark:border-red-600';
                    bg = 'bg-red-50 dark:bg-red-900/20';
                  }

                  return (
                    <div key={o.id} className={`flex items-start gap-3 p-3 rounded-lg border text-sm ${border} ${bg}`}>
                      <div className="flex-shrink-0 mt-0.5">
                        {selected ? (
                          <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${
                            correct ? 'border-green-500 bg-green-500' : 'border-red-500 bg-red-500'
                          }`}>
                            <div className="w-1.5 h-1.5 rounded-full bg-white" />
                          </div>
                        ) : (
                          <div className="w-4 h-4 rounded-full border-2 border-gray-300 dark:border-gray-600" />
                        )}
                      </div>
                      <div className="flex-1 min-w-0"><LatexText text={o.text_md} /></div>
                      {correct && (
                        <span className="flex-shrink-0 text-xs font-medium text-green-600 dark:text-green-400">✓ верный</span>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            {q.q_type === 'short' && (
              <div className="space-y-2 mb-3">
                <div className={`flex items-center gap-2 p-3 rounded-lg border text-sm ${
                  q.text_answer
                    ? q.is_correct
                      ? 'border-green-400 bg-green-50 dark:border-green-600 dark:bg-green-900/20'
                      : 'border-red-400 bg-red-50 dark:border-red-600 dark:bg-red-900/20'
                    : 'border-gray-300 bg-gray-50 dark:border-gray-600 dark:bg-gray-800'
                }`}>
                  <span className="text-gray-500 dark:text-gray-400">Ответ ученика:</span>
                  <span className={`font-medium ${
                    !q.text_answer ? 'text-gray-400 dark:text-gray-500' : q.is_correct ? 'text-green-700 dark:text-green-300' : 'text-red-600 dark:text-red-400'
                  }`}>
                    {q.text_answer || '(не указан)'}
                  </span>
                </div>
                {q.accepted_answers && (
                  <div className="flex items-center gap-2 p-3 rounded-lg border border-green-300 dark:border-green-700 text-sm">
                    <span className="text-gray-500 dark:text-gray-400">Правильный:</span>
                    <span className="font-medium text-green-700 dark:text-green-300">{q.accepted_answers.join(', ')}</span>
                  </div>
                )}
              </div>
            )}

            {q.explanation_md && (
              <div className="mt-3 p-3 bg-blue-50 rounded-lg border border-blue-200 text-sm text-blue-800 dark:bg-blue-900/20 dark:border-blue-800 dark:text-blue-300">
                <RichText text={q.explanation_md} />
              </div>
            )}
          </div>
        ))}
      </main>
    </div>
  );
}
