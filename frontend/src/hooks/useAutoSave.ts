import { useEffect, useRef } from 'react';
import type { AnswerSave } from '../types/quiz';
import { studentApi } from '../api/endpoints';

export function useAutoSave(attemptId: number | null, sessionToken: string | null, answers: AnswerSave[], intervalMs = 60000) {
  const answersRef = useRef(answers);
  answersRef.current = answers;

  useEffect(() => {
    if (!attemptId || !sessionToken) return;
    const id = setInterval(() => {
      const nonEmpty = answersRef.current.filter(
        (a) => (a.selected_option_ids && a.selected_option_ids.length > 0) || a.text_answer,
      );
      if (nonEmpty.length > 0) {
        studentApi.saveAnswers(attemptId, nonEmpty, sessionToken).catch(() => {
          localStorage.setItem(`backup_${attemptId}`, JSON.stringify(answersRef.current));
        });
      }
    }, intervalMs);
    return () => clearInterval(id);
  }, [attemptId, sessionToken, intervalMs]);
}
