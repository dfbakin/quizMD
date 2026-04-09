import {
  createContext,
  createElement,
  useState,
  useCallback,
  useMemo,
  useContext,
  useEffect,
  type ReactNode,
} from 'react';
import type { TokenResponse } from '../types/quiz';

interface User {
  user_id: number;
  display_name: string;
  role: 'teacher' | 'student';
}

interface AuthContextValue {
  user: User | null;
  login: (data: TokenResponse) => void;
  logout: () => void;
}

function loadUser(): User | null {
  const raw = localStorage.getItem('user');
  try {
    return raw ? (JSON.parse(raw) as User) : null;
  } catch {
    return null;
  }
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
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

  // Keep state in sync if storage changes from another browser tab.
  useEffect(() => {
    const onStorage = (event: StorageEvent) => {
      if (event.key === 'user' || event.key === 'access_token') {
        setUser(loadUser());
      }
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  const value = useMemo(() => ({ user, login, logout }), [user, login, logout]);
  return createElement(AuthContext.Provider, { value }, children);
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return ctx;
}
