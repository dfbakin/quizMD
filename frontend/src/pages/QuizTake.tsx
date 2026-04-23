import { useEffect, useState, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { studentApi } from '../api/endpoints';
import type { AttemptStart, AnswerSave } from '../types/quiz';
import QuizQuestion from '../components/QuizQuestion';
import Timer from '../components/Timer';
import { useHeartbeat, type HeartbeatAnchor } from '../hooks/useHeartbeat';
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

const SUBMIT_MAX_RETRIES = 4;

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

export default function QuizTake() {
  const { assignmentId } = useParams<{ assignmentId: string }>();
  const navigate = useNavigate();
  const [attempt, setAttempt] = useState<AttemptStart | null>(null);
  const [answers, setAnswers] = useState<AnswerSave[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState('');
  const [submitError, setSubmitError] = useState('');
  const [anchor, setAnchor] = useState<HeartbeatAnchor | null>(null);
  const invalidatedRef = useRef(false);
  const submittingOnceRef = useRef(false);

  useEffect(() => {
    if (!assignmentId) return;
    studentApi.startAttempt(Number(assignmentId)).then((r) => {
      const data = r.data;
      setAttempt(data);
      setAnchor({ serverNow: data.server_now, deadlineAt: data.deadline_at });
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

  const updateAnswer = useCallback((updated: AnswerSave) => {
    setAnswers((prev) => prev.map((a) => (a.question_id === updated.question_id ? updated : a)));
  }, []);

  // Hold a ref to current answers so the heartbeat hook can read them without
  // re-subscribing on every keystroke (Bug E mitigation extends here too).
  const answersRef = useRef(answers);
  useEffect(() => {
    answersRef.current = answers;
  }, [answers]);

  const handleSubmit = useCallback(async () => {
    if (!attempt || submittingOnceRef.current || submitted) return;
    submittingOnceRef.current = true;
    setSubmitting(true);
    setSubmitError('');

    let lastErr: unknown = null;
    for (let attemptN = 0; attemptN < SUBMIT_MAX_RETRIES; attemptN++) {
      try {
        await studentApi.submitAttempt(
          attempt.attempt_id,
          answersRef.current,
          attempt.session_token,
        );
        try {
          localStorage.removeItem(`backup_${attempt.attempt_id}`);
        } catch {
          /* ignore */
        }
        setSubmitted(true);
        setSubmitting(false);
        return;
      } catch (err: unknown) {
        lastErr = err;
        const status = getStatusCode(err);
        // 409 means server already considers us submitted (e.g. background
        // sweep beat us to it) — treat as success.
        if (status === 409) {
          setSubmitted(true);
          setSubmitting(false);
          return;
        }
        if (status === 404) {
          handleAttemptInvalidated();
          setSubmitting(false);
          return;
        }
        const backoff = Math.min(8_000, 500 * 2 ** attemptN);
        await sleep(backoff);
      }
    }
    // Out of retries — leave the screen in "Submitting…" with a retry button
    // and allow another attempt. localStorage snapshot from useHeartbeat
    // remains available for next session.
    submittingOnceRef.current = false;
    setSubmitting(false);
    setSubmitError(
      getErrorDetail(lastErr) ||
        'Не удалось отправить ответы. Проверьте соединение и попробуйте ещё раз.',
    );
  }, [attempt, submitted, handleAttemptInvalidated]);

  const handleHeartbeatExpired = useCallback(() => {
    void handleSubmit();
  }, [handleSubmit]);

  const handleAnchor = useCallback((next: HeartbeatAnchor) => {
    setAnchor(next);
  }, []);

  const getAnswers = useCallback(() => answersRef.current, []);

  useHeartbeat({
    attemptId: attempt?.attempt_id ?? null,
    sessionToken: attempt?.session_token ?? null,
    getAnswers,
    onAnchor: handleAnchor,
    onInvalidated: handleAttemptInvalidated,
    onExpired: handleHeartbeatExpired,
  });

  const handleExpire = useCallback(() => {
    void handleSubmit();
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

  if (!attempt || !anchor) {
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
            <Timer
              deadlineAt={anchor.deadlineAt}
              serverNowAtAnchor={anchor.serverNow}
              onExpire={handleExpire}
            />
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
        {submitError && (
          <div className="max-w-3xl mx-auto px-4 pb-3">
            <div className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-700 dark:bg-red-900/40 dark:text-red-300 flex items-center justify-between gap-3">
              <span>{submitError}</span>
              <button
                onClick={() => void handleSubmit()}
                className="font-medium underline-offset-2 hover:underline"
              >
                Повторить
              </button>
            </div>
          </div>
        )}
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
      </main>
    </div>
  );
}
