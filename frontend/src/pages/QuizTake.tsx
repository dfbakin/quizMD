import { useEffect, useState, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { studentApi } from '../api/endpoints';
import type { AttemptStart, AnswerSave } from '../types/quiz';
import QuizQuestion from '../components/QuizQuestion';
import Timer from '../components/Timer';
import { useAutoSave } from '../hooks/useAutoSave';
import ThemeToggle from '../components/ThemeToggle';

function getStatusCode(err: unknown): number | undefined {
  if (typeof err === 'object' && err !== null && 'response' in err) {
    return (err as { response?: { status?: number } }).response?.status;
  }
  return undefined;
}

function getErrorDetail(err: unknown): string | undefined {
  if (typeof err === 'object' && err !== null && 'response' in err) {
    const detail = (err as { response?: { data?: { detail?: unknown } } }).response?.data?.detail;
    if (typeof detail === 'string') return detail;
  }
  return undefined;
}

export default function QuizTake() {
  const { assignmentId } = useParams<{ assignmentId: string }>();
  const navigate = useNavigate();
  const [attempt, setAttempt] = useState<AttemptStart | null>(null);
  const [answers, setAnswers] = useState<AnswerSave[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState('');
  const invalidatedRef = useRef(false);

  useEffect(() => {
    if (!assignmentId) return;
    studentApi.startAttempt(Number(assignmentId)).then((r) => {
      const data = r.data;
      setAttempt(data);
      const savedMap = new Map(
        (data.saved_answers || []).map((a) => [a.question_id, a]),
      );
      setAnswers(data.questions.map((q) => {
        const saved = savedMap.get(q.id);
        if (saved) {
          return {
            question_id: q.id,
            selected_option_ids: saved.selected_option_ids ?? undefined,
            text_answer: saved.text_answer ?? undefined,
          };
        }
        return { question_id: q.id };
      }));
    }).catch((err: unknown) => {
      if (getStatusCode(err) === 409) {
        setSubmitted(true);
      } else {
        setError(getErrorDetail(err) || 'Не удалось начать тест');
      }
    });
  }, [assignmentId]);

  const handleAttemptInvalidated = useCallback(() => {
    if (invalidatedRef.current) return;
    invalidatedRef.current = true;
    window.alert('Попытка была сброшена преподавателем. Вы возвращены к списку тестов.');
    navigate('/student', { replace: true });
  }, [navigate]);

  useAutoSave(attempt?.attempt_id ?? null, attempt?.session_token ?? null, answers, 60000, handleAttemptInvalidated);

  const updateAnswer = useCallback((updated: AnswerSave) => {
    setAnswers((prev) => prev.map((a) => (a.question_id === updated.question_id ? updated : a)));
  }, []);

  const handleSubmit = useCallback(async () => {
    if (!attempt || submitting || submitted) return;
    setSubmitting(true);
    try {
      await studentApi.submitAttempt(attempt.attempt_id, answers, attempt.session_token);
      setSubmitted(true);
    } catch (err: unknown) {
      if (getStatusCode(err) === 409) {
        setSubmitted(true);
      } else if (getStatusCode(err) === 404) {
        handleAttemptInvalidated();
      } else {
        setError('Ошибка при отправке');
      }
    }
    setSubmitting(false);
  }, [attempt, answers, submitting, submitted, handleAttemptInvalidated]);

  const handleExpire = useCallback(() => {
    handleSubmit();
  }, [handleSubmit]);

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950">
        <div className="bg-white dark:bg-gray-900 rounded-xl shadow p-8 text-center max-w-md">
          <p className="text-red-500 dark:text-red-400 mb-4">{error}</p>
          <button onClick={() => navigate('/student')} className="text-blue-600 hover:underline dark:text-blue-400 dark:hover:text-blue-300">
            Вернуться
          </button>
        </div>
      </div>
    );
  }

  if (submitted) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950">
        <div className="bg-white dark:bg-gray-900 rounded-xl shadow p-8 text-center max-w-md">
          <div className="text-4xl mb-4">&#10003;</div>
          <h2 className="text-xl font-bold text-gray-800 dark:text-gray-100 mb-2">Тест отправлен</h2>
          <p className="text-gray-500 dark:text-gray-400 mb-6">Результаты будут доступны после проверки преподавателем.</p>
          <button
            onClick={() => navigate('/student')}
            className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600 transition"
          >
            К списку тестов
          </button>
        </div>
      </div>
    );
  }

  if (!attempt) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950">
        <p className="text-gray-500 dark:text-gray-400">Загрузка теста...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950">
      <header className="sticky top-0 z-50 bg-white dark:bg-gray-900 shadow-sm border-b border-gray-200 dark:border-gray-700">
        <div className="max-w-3xl mx-auto px-4 py-3 flex justify-between items-center">
          <h1 className="text-lg font-bold text-gray-800 dark:text-gray-100 truncate">Тест</h1>
          <div className="flex items-center gap-4">
            {attempt.time_limit_minutes && (
              <Timer
                deadlineAt={attempt.deadline_at}
                serverNow={attempt.server_now}
                onExpire={handleExpire}
              />
            )}
            <ThemeToggle />
            <button
              onClick={handleSubmit}
              disabled={submitting}
              className="bg-green-600 text-white px-5 py-2 rounded-lg font-medium hover:bg-green-700 disabled:opacity-50 dark:bg-green-500 dark:hover:bg-green-600 transition"
            >
              {submitting ? 'Отправка...' : 'Отправить'}
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-6">
        {attempt.questions.map((q, i) => (
          <QuizQuestion
            key={q.id}
            question={q}
            index={i}
            answer={answers.find((a) => a.question_id === q.id) || { question_id: q.id }}
            onChange={updateAnswer}
          />
        ))}

        <div className="mt-6 mb-12 text-center">
          <button
            onClick={handleSubmit}
            disabled={submitting}
            className="bg-green-600 text-white px-8 py-3 rounded-lg font-medium text-lg hover:bg-green-700 disabled:opacity-50 dark:bg-green-500 dark:hover:bg-green-600 transition"
          >
            {submitting ? 'Отправка...' : 'Отправить тест'}
          </button>
        </div>
      </main>
    </div>
  );
}
