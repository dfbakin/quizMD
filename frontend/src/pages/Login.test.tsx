import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

import Login from './Login';
import { AuthProvider } from '../hooks/useAuth';
import { authApi } from '../api/endpoints';

function renderLogin() {
  return render(
    <AuthProvider>
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    </AuthProvider>,
  );
}

describe('Login show-password toggle', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('starts hidden, toggles to text on click, and back', async () => {
    const user = userEvent.setup();
    renderLogin();

    const password = screen.getByLabelText('Пароль') as HTMLInputElement;
    expect(password.type).toBe('password');

    const toggle = screen.getByRole('button', { name: /Показать пароль/i });
    expect(toggle).toHaveAttribute('aria-pressed', 'false');

    await user.click(toggle);
    expect(password.type).toBe('text');
    expect(
      screen.getByRole('button', { name: /Скрыть пароль/i }),
    ).toHaveAttribute('aria-pressed', 'true');

    await user.click(screen.getByRole('button', { name: /Скрыть пароль/i }));
    expect(password.type).toBe('password');
  });

  it('hides the password again on submit (success or failure)', async () => {
    vi.spyOn(authApi, 'login').mockRejectedValueOnce(new Error('bad creds'));
    const user = userEvent.setup();
    renderLogin();

    const password = screen.getByLabelText('Пароль') as HTMLInputElement;
    await user.type(screen.getByLabelText('Логин'), 'u');
    await user.type(password, 'p');
    await user.click(screen.getByRole('button', { name: /Показать пароль/i }));
    expect(password.type).toBe('text');

    await user.click(screen.getByRole('button', { name: /Войти/i }));
    expect(password.type).toBe('password');
  });
});
