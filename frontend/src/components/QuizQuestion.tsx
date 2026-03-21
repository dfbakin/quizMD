import RichText from './RichText';
import LatexText from './LatexText';
import type { Question, AnswerSave } from '../types/quiz';

interface Props {
  question: Question;
  index: number;
  answer: AnswerSave;
  onChange: (answer: AnswerSave) => void;
}

export default function QuizQuestion({ question, index, answer, onChange }: Props) {
  const handleSingle = (optionId: number) => {
    onChange({ question_id: question.id, selected_option_ids: [optionId] });
  };

  const handleMultiple = (optionId: number, checked: boolean) => {
    const current = answer.selected_option_ids || [];
    const next = checked ? [...current, optionId] : current.filter((id) => id !== optionId);
    onChange({ question_id: question.id, selected_option_ids: next });
  };

  const handleText = (value: string) => {
    onChange({ question_id: question.id, text_answer: value });
  };

  return (
    <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6 mb-4">
      <h3 className="text-base font-semibold text-gray-700 dark:text-gray-200 mb-1">
        Вопрос {index + 1}. {question.title}
      </h3>
      <p className="text-xs text-gray-400 dark:text-gray-500 mb-3">
        {question.q_type === 'single' && 'Один вариант ответа'}
        {question.q_type === 'multiple' && 'Несколько вариантов ответа'}
        {question.q_type === 'short' && 'Краткий ответ'}
        {' · '}{question.points} {question.points === 1 ? 'балл' : 'балла'}
      </p>

      <RichText text={question.body_md} className="text-gray-800 dark:text-gray-100 mb-4 leading-relaxed" />

      {question.q_type === 'single' && (
        <div className="space-y-2">
          {question.options.map((o) => (
            <label
              key={o.id}
              className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                answer.selected_option_ids?.includes(o.id)
                  ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30'
                  : 'border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800'
              }`}
            >
              <input
                type="radio"
                name={`q-${question.id}`}
                checked={answer.selected_option_ids?.includes(o.id) || false}
                onChange={() => handleSingle(o.id)}
                className="mt-1 accent-blue-600"
              />
              <LatexText text={o.text_md} />
            </label>
          ))}
        </div>
      )}

      {question.q_type === 'multiple' && (
        <div className="space-y-2">
          {question.options.map((o) => (
            <label
              key={o.id}
              className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                answer.selected_option_ids?.includes(o.id)
                  ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30'
                  : 'border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800'
              }`}
            >
              <input
                type="checkbox"
                checked={answer.selected_option_ids?.includes(o.id) || false}
                onChange={(e) => handleMultiple(o.id, e.target.checked)}
                className="mt-1 accent-blue-600"
              />
              <LatexText text={o.text_md} />
            </label>
          ))}
        </div>
      )}

      {question.q_type === 'short' && (
        <input
          type="text"
          value={answer.text_answer || ''}
          onChange={(e) => handleText(e.target.value)}
          placeholder="Введите ответ..."
          className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      )}
    </div>
  );
}
