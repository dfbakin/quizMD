import { describe, expect, it } from 'vitest';
import { render, waitFor } from '@testing-library/react';

import QuizQuestion from './QuizQuestion';
import type { AnswerSave, Question } from '../types/quiz';

describe('QuizQuestion heading latex rendering', () => {
  it('renders katex markup for latex in title heading', async () => {
    const question: Question = {
      id: 1,
      order_index: 0,
      q_type: 'single',
      title: 'Предел $x^2$',
      body_md: 'Выберите правильный ответ.',
      points: 1,
      options: [
        { id: 10, order_index: 0, text_md: '1' },
        { id: 11, order_index: 1, text_md: '2' },
      ],
    };
    const answer: AnswerSave = { question_id: 1, selected_option_ids: [] };

    const { container } = render(
      <QuizQuestion
        question={question}
        index={0}
        answer={answer}
        onChange={() => {}}
      />,
    );

    await waitFor(() => {
      expect(container.querySelector('h3 .katex')).not.toBeNull();
    });
  });
});
