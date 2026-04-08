import { useState, useEffect } from 'react';
import { authApi, getToken, clearToken, type UserInfo } from '../services/api';

export function useAuth() {
  const [user, setUser]       = useState<UserInfo | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (getToken()) {
      authApi.me()
        .then(setUser)
        .catch(() => clearToken())
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const logout = () => {
    clearToken();
    setUser(null);
    window.location.href = '/login';
  };

  return { user, loading, setUser, logout };
}
