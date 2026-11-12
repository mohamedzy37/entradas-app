import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { api, type LoginPayload, type RegisterPayload } from '../api/client';
import type { Role, User } from '../api/types';
import {
  clearSession,
  ensureAccessToken,
  hasStoredSession,
  markSessionHint,
  setSessionExpiredHandler,
} from './tokenStore';

interface AuthContextValue {
  /** Usuario autenticado o null si es anonimo. */
  user: User | null;
  /** true mientras se comprueba la sesion inicial. */
  loading: boolean;
  register: (payload: RegisterPayload) => Promise<void>;
  login: (payload: LoginPayload) => Promise<void>;
  logout: () => Promise<void>;
  /**
   * Completa un login externo (Google): el backend ya dejo la cookie del
   * refresh; aqui se obtiene el access token y el usuario. true si hay sesion.
   */
  completeExternalLogin: () => Promise<boolean>;
  /** true si el usuario tiene uno de los roles indicados. */
  hasRole: (...roles: Role[]) => boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

/**
 * La sesion se compone de:
 *  - access token JWT de vida corta, guardado SOLO en memoria;
 *  - refresh token JWT en cookie HttpOnly (JavaScript no puede leerlo).
 * El backend no guarda ninguna sesion.
 *
 * Al arrancar, si hay indicios de sesion se pide un access token nuevo y
 * se consulta /auth/me para recuperar el usuario. El rol se lee siempre del
 * servidor, por lo que un cambio de rol se aplica al instante.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  // Si el refresh deja de ser valido (revocado, reutilizado o caducado),
  // tokenStore avisa y aqui se limpia la sesion.
  useEffect(() => {
    setSessionExpiredHandler(() => setUser(null));
    return () => setSessionExpiredHandler(null);
  }, []);

  useEffect(() => {
    let active = true;

    async function bootstrap() {
      if (!hasStoredSession()) {
        if (active) setLoading(false);
        return;
      }
      const token = await ensureAccessToken();
      if (!token) {
        if (active) setLoading(false);
        return;
      }
      try {
        const response = await api.me();
        if (active) setUser(response.data.user);
      } catch {
        if (active) {
          clearSession();
          setUser(null);
        }
      } finally {
        if (active) setLoading(false);
      }
    }

    void bootstrap();
    return () => {
      active = false;
    };
  }, []);

  const register = useCallback(async (payload: RegisterPayload) => {
    const response = await api.register(payload);
    setUser(response.data.user);
  }, []);

  const login = useCallback(async (payload: LoginPayload) => {
    const response = await api.login(payload);
    setUser(response.data.user);
  }, []);

  const completeExternalLogin = useCallback(async () => {
    markSessionHint();
    const token = await ensureAccessToken({ force: true });
    if (!token) return false;
    try {
      const response = await api.me();
      setUser(response.data.user);
      return true;
    } catch {
      clearSession();
      setUser(null);
      return false;
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      clearSession();
      setUser(null);
    }
  }, []);

  const hasRole = useCallback(
    (...roles: Role[]) => (user ? roles.includes(user.role) : false),
    [user],
  );

  const value = useMemo<AuthContextValue>(
    () => ({ user, loading, register, login, logout, completeExternalLogin, hasRole }),
    [user, loading, register, login, logout, completeExternalLogin, hasRole],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth debe usarse dentro de <AuthProvider>');
  }
  return context;
}
