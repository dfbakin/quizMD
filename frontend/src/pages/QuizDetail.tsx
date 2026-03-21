import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { quizApi } from '../api/endpoints';
import type { QuizDetail as QuizDetailType } from '../types/quiz';
import RichText from '../components/RichText';
import LatexText from '../components/LatexText';
import ThemeToggle from '../components/ThemeToggle';

export default function QuizDetail() {
  const { quizId } = useParams<{ quizId: string }>();
  const navigate = useNavigate();
  const [quiz, setQuiz] = useState<QuizDetailType | null>(null);

  useEffect(() => {
    if (!quizId) return;
    quizApi.get(Number(quizId)).then((r) => setQuiz(r.data));
  }, [quizId]);

  if (!quiz) {
    return <div className="min-h-screen flex items-center justify-center"><p className="text-gray-500 dark:text-gray-400">Загрузка...</p></div>;
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950">
      <header className="bg-white dark:bg-gray-900 shadow-sm border-b border-gray-200 dark:border-gray-700">
        <div className="max-w-3xl mx-auto px-4 py-4 flex justify-between items-center">
          <div>
            <h1 className="text-xl font-bold text-gray-800 dark:text-gray-100">{quiz.title}</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {quiz.question_count} вопросов · {quiz.time_limit_minutes ? `${quiz.time_limit_minutes} мин` : 'без лимита'}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <button onClick={() => navigate('/teacher')} className="text-sm text-gray-500 dark:text-gray-400 hover:text-blue-600 transition">Назад</button>
          </div>
        </div>
      </header>
      <main className="max-w-3xl mx-auto px-4 py-6">
        {quiz.questions.map((q, i) => (
          <div key={q.id} className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 p-6 mb-4 shadow-sm">
            <h3 className="font-semibold text-gray-700 dark:text-gray-200 mb-1">Вопрос {i + 1}. {q.title}</h3>
            <p className="text-xs text-gray-400 dark:text-gray-500 mb-3">{q.q_type} · {q.points} б.</p>
            <RichText text={q.body_md} className="text-gray-700 dark:text-gray-200 mb-3 text-sm" />
            {q.options.length > 0 && (
              <div className="space-y-1.5 mb-3">
                {q.options.map((o) => (
                  <div key={o.id} className={`p-2.5 rounded-lg border text-sm ${o.is_correct ? 'bg-green-50 dark:bg-green-900/30 border-green-300 dark:border-green-700 font-medium' : 'border-gray-200 dark:border-gray-700'}`}>
                    <LatexText text={o.text_md} />
                  </div>
                ))}
              </div>
            )}
            {q.accepted_answers && q.accepted_answers.length > 0 && (
              <p className="text-sm text-green-600 dark:text-green-400 mb-2">Ответ: {q.accepted_answers.join(', ')}</p>
            )}
            {q.explanation_md && (
              <div className="mt-2 p-3 bg-blue-50 dark:bg-blue-900/30 rounded-lg border border-blue-200 dark:border-blue-800 text-sm text-blue-800 dark:text-blue-300">
                <RichText text={q.explanation_md} />
              </div>
            )}
          </div>
        ))}
      </main>
    </div>
  );
}
