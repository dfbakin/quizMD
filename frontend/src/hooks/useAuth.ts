import { useState, useCallback } from 'react';
import type { TokenResponse } from '../types/quiz';

interface User {
  user_id: number;
  display_name: string;
  role: 'teacher' | 'student';
}

function loadUser(): User | null {
  const raw = localStorage.getItem('user');
  return raw ? JSON.parse(raw) : null;
}

export function useAuth() {
  const [user, setUser] = useState<User | null>(loadUser);

  const login = useCallback((data: TokenResponse) => {
    localStorage.setItem('access_token', data.access_token);
    const u: User = { user_id: data.user_id, display_name: data.display_name, role: data.role };
    localStorage.setItem('user', JSON.stringify(u));
    setUser(u);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user');
    setUser(null);
  }, []);

  return { user, login, logout };
}
