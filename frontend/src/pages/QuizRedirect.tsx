import { useEffect, useState } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { assignmentApi } from '../api/endpoints';
import { useAuth } from '../hooks/useAuth';

export default function QuizRedirect() {
  const { shareCode } = useParams<{ shareCode: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [error, setError] = useState('');

  useEffect(() => {
    if (!shareCode) return;
    assignmentApi.lookupByCode(shareCode).then((r) => {
      const { assignment_id } = r.data;
      if (user && user.role === 'student') {
        navigate(`/student/quiz/${assignment_id}`, { replace: true });
      } else {
        navigate(`/login?next=/quiz/${shareCode}`, { replace: true });
      }
    }).catch(() => {
      setError('Тест не найден');
    });
  }, [shareCode, user, navigate]);

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950">
        <div className="bg-white dark:bg-gray-900 rounded-xl shadow p-8 text-center">
          <p className="text-red-500 mb-4">{error}</p>
          <button onClick={() => navigate('/login')} className="text-blue-600 dark:text-blue-400 hover:underline">
            На страницу входа
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950">
      <p className="text-gray-500 dark:text-gray-400">Перенаправление...</p>
    </div>
  );
}
