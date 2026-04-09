import { beforeEach, describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import { AuthProvider, useAuth } from './useAuth';
import { ProtectedRoute } from '../App';

function AuthTestPanel() {
  const { user, login, logout } = useAuth();
  return (
    <div>
      <div data-testid="user-name">{user?.display_name ?? 'none'}</div>
      <button
        type="button"
        onClick={() =>
          login({
            access_token: 'token-1',
            token_type: 'bearer',
            role: 'teacher',
            user_id: 1,
            display_name: 'Teacher A',
          })
        }
      >
        Login
      </button>
      <button type="button" onClick={logout}>Logout</button>
    </div>
  );
}

function TeacherProtectedPage() {
  const { logout } = useAuth();
  return <button type="button" onClick={logout}>Logout</button>;
}

describe('useAuth shared provider', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('propagates login and logout across consumers', async () => {
    const user = userEvent.setup();
    render(
      <AuthProvider>
        <AuthTestPanel />
      </AuthProvider>,
    );

    expect(screen.getByTestId('user-name')).toHaveTextContent('none');

    await user.click(screen.getByRole('button', { name: 'Login' }));
    expect(screen.getByTestId('user-name')).toHaveTextContent('Teacher A');
    expect(localStorage.getItem('user')).toContain('Teacher A');

    await user.click(screen.getByRole('button', { name: 'Logout' }));
    expect(screen.getByTestId('user-name')).toHaveTextContent('none');
    expect(localStorage.getItem('user')).toBeNull();
    expect(localStorage.getItem('access_token')).toBeNull();
  });

  it('redirects protected route to login after logout', async () => {
    localStorage.setItem('access_token', 'token-1');
    localStorage.setItem('user', JSON.stringify({
      user_id: 1,
      display_name: 'Teacher A',
      role: 'teacher',
    }));
    const user = userEvent.setup();

    render(
      <AuthProvider>
        <MemoryRouter initialEntries={['/teacher']}>
          <Routes>
            <Route path="/login" element={<div>Login Page</div>} />
            <Route path="/student" element={<div>Student Page</div>} />
            <Route
              path="/teacher"
              element={(
                <ProtectedRoute requiredRole="teacher">
                  <TeacherProtectedPage />
                </ProtectedRoute>
              )}
            />
          </Routes>
        </MemoryRouter>
      </AuthProvider>,
    );

    await user.click(screen.getByRole('button', { name: 'Logout' }));
    expect(screen.getByText('Login Page')).toBeInTheDocument();
  });
});
