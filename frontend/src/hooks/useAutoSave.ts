import { useEffect, useRef } from 'react';
import type { AnswerSave } from '../types/quiz';
import { studentApi } from '../api/endpoints';

function getStatusCode(err: unknown): number | undefined {
  if (typeof err === 'object' && err !== null && 'response' in err) {
    return (err as { response?: { status?: number } }).response?.status;
  }
  return undefined;
}

export function useAutoSave(
  attemptId: number | null,
  sessionToken: string | null,
  answers: AnswerSave[],
  intervalMs = 60000,
  onAttemptInvalidated?: () => void,
) {
  const answersRef = useRef(answers);
  useEffect(() => {
    answersRef.current = answers;
  }, [answers]);

  useEffect(() => {
    if (!attemptId || !sessionToken) return;
    const id = setInterval(() => {
      const nonEmpty = answersRef.current.filter(
        (a) => (a.selected_option_ids && a.selected_option_ids.length > 0) || a.text_answer,
      );
      if (nonEmpty.length > 0) {
        studentApi.saveAnswers(attemptId, nonEmpty, sessionToken).catch((err: unknown) => {
          if (getStatusCode(err) === 404) {
            onAttemptInvalidated?.();
            return;
          }
          localStorage.setItem(`backup_${attemptId}`, JSON.stringify(answersRef.current));
        });
      }
    }, intervalMs);
    return () => clearInterval(id);
  }, [attemptId, sessionToken, intervalMs, onAttemptInvalidated]);
}
