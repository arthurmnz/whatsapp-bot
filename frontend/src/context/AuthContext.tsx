import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { api, getStoredToken, setStoredToken, setUnauthorizedHandler } from '../lib/api';
import type { UserSummary } from '../types/api';

interface AuthContextValue {
  token: string | null;
  user: UserSummary | null;
  loading: boolean;
  sessionNotice: string | null;
  loginWithToken: (token: string, user: UserSummary) => void;
  refreshUser: () => Promise<void>;
  logout: (notice?: string) => void;
  hasPermission: (code: string) => boolean;
  clearSessionNotice: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(() => getStoredToken());
  const [user, setUser] = useState<UserSummary | null>(null);
  const [loading, setLoading] = useState<boolean>(() => Boolean(getStoredToken()));
  const [sessionNotice, setSessionNotice] = useState<string | null>(null);

  const logout = useCallback((notice?: string) => {
    setStoredToken(null);
    setToken(null);
    setUser(null);
    if (notice) {
      setSessionNotice(notice);
    }
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      logout('Sua sessão expirou ou foi invalidada. Faça login novamente.');
    });
    return () => setUnauthorizedHandler(null);
  }, [logout]);

  const refreshUser = useCallback(async () => {
    const activeToken = getStoredToken();
    if (!activeToken) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const data = await api.auth.me();
      setUser(data.user);
      setToken(activeToken);
    } catch {
      setStoredToken(null);
      setToken(null);
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshUser();
  }, [refreshUser]);

  const loginWithToken = useCallback((newToken: string, loggedUser: UserSummary) => {
    setStoredToken(newToken);
    setToken(newToken);
    setUser(loggedUser);
    setSessionNotice(null);
    setLoading(false);
  }, []);

  const hasPermission = useCallback(
    (code: string) => {
      if (!user) return false;
      if (user.role === 'admin') return true;
      return user.permissions.includes(code);
    },
    [user],
  );

  const clearSessionNotice = useCallback(() => setSessionNotice(null), []);

  return (
    <AuthContext.Provider
      value={{
        token,
        user,
        loading,
        sessionNotice,
        loginWithToken,
        refreshUser,
        logout,
        hasPermission,
        clearSessionNotice,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth deve ser utilizado dentro de AuthProvider');
  }
  return ctx;
}
