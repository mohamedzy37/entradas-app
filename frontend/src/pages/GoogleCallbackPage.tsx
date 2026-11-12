import { useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { Loading } from '../components/StateViews';

/** Solo rutas internas como destino (evita redirecciones abiertas). */
function safeNext(value: string | null): string {
  if (!value || !value.startsWith('/') || value.startsWith('//') || value.startsWith('/\\')) {
    return '/';
  }
  return value;
}

/**
 * Vuelta del login con Google. El backend ya ha verificado la identidad y ha
 * dejado la cookie HttpOnly del refresh token; aqui se pide el access token
 * (POST /auth/refresh), se carga el usuario y se navega al destino.
 */
export function GoogleCallbackPage() {
  const { completeExternalLogin } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const started = useRef(false);

  useEffect(() => {
    // En desarrollo React ejecuta los efectos dos veces: solo un refresco.
    if (started.current) return;
    started.current = true;

    const next = safeNext(params.get('next'));
    void completeExternalLogin().then((ok) => {
      navigate(ok ? next : '/acceder?error=google', { replace: true });
    });
  }, [completeExternalLogin, navigate, params]);

  return <Loading label="Completando el inicio de sesión con Google..." />;
}
