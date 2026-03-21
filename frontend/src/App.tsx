import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './hooks/useAuth';
import { useTheme } from './hooks/useTheme';
import Login from './pages/Login';
import StudentDashboard from './pages/StudentDashboard';
import QuizTake from './pages/QuizTake';
import QuizResults from './pages/QuizResults';
import TeacherDashboard from './pages/TeacherDashboard';
import QuizDetail from './pages/QuizDetail';
import GroupManage from './pages/GroupManage';
import AssignmentResults from './pages/AssignmentResults';
import TeacherAttemptDetail from './pages/TeacherAttemptDetail';
import QuizRedirect from './pages/QuizRedirect';

function ProtectedRoute({ children, requiredRole }: { children: React.ReactNode; requiredRole?: string }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" />;
  if (requiredRole && user.role !== requiredRole) {
    return <Navigate to={user.role === 'teacher' ? '/teacher' : '/student'} />;
  }
  return <>{children}</>;
}

export default function App() {
  const { user } = useAuth();
  useTheme();

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={user ? <Navigate to={user.role === 'teacher' ? '/teacher' : '/student'} /> : <Login />} />
        <Route path="/quiz/:shareCode" element={<QuizRedirect />} />
        <Route path="/student" element={<ProtectedRoute requiredRole="student"><StudentDashboard /></ProtectedRoute>} />
        <Route path="/student/quiz/:assignmentId" element={<ProtectedRoute requiredRole="student"><QuizTake /></ProtectedRoute>} />
        <Route path="/student/results/:attemptId" element={<ProtectedRoute requiredRole="student"><QuizResults /></ProtectedRoute>} />
        <Route path="/teacher" element={<ProtectedRoute requiredRole="teacher"><TeacherDashboard /></ProtectedRoute>} />
        <Route path="/teacher/quiz/:quizId" element={<ProtectedRoute requiredRole="teacher"><QuizDetail /></ProtectedRoute>} />
        <Route path="/teacher/group/:groupId" element={<ProtectedRoute requiredRole="teacher"><GroupManage /></ProtectedRoute>} />
        <Route path="/teacher/assignment/:assignmentId/results" element={<ProtectedRoute requiredRole="teacher"><AssignmentResults /></ProtectedRoute>} />
        <Route path="/teacher/assignment/:assignmentId/attempts/:attemptId" element={<ProtectedRoute requiredRole="teacher"><TeacherAttemptDetail /></ProtectedRoute>} />
        <Route path="*" element={<Navigate to="/login" />} />
      </Routes>
    </BrowserRouter>
  );
}
