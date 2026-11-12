import { useState, type FormEvent } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { ApiError } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { AlertIcon, UserIcon } from '../components/Icons';

interface LocationState {
  from?: { pathname: string; search?: string };
}

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const from = (location.state as LocationState | null)?.from;
  const redirectTo = from ? `${from.pathname}${from.search ?? ''}` : '/';

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);

    if (!email.trim() || !password) {
      setError('Introduce tu correo y tu contraseña.');
      return;
    }

    setSubmitting(true);
    try {
      await login({ email: email.trim(), password });
      navigate(redirectTo, { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'No se pudo iniciar sesión.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-md px-4 py-10">
      <div className="text-center">
        <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-sky/10 text-sky">
          <UserIcon />
        </span>
        <h1 className="mt-3 text-2xl font-extrabold text-ink">Inicia sesión</h1>
        <p className="mt-1 text-sm text-muted">
          Necesitas una cuenta para comprar entradas.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="mt-6 rounded-xl border border-line bg-white p-5">
        <label className="block">
          <span className="mb-1 block text-sm font-semibold text-ink">Correo electrónico</span>
          <input
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="ana@ejemplo.com"
            className="w-full rounded-md border border-line px-3 py-3 text-sm outline-none focus:border-sky focus:ring-2 focus:ring-sky/30"
          />
        </label>

        <label className="mt-4 block">
          <span className="mb-1 block text-sm font-semibold text-ink">Contraseña</span>
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            className="w-full rounded-md border border-line px-3 py-3 text-sm outline-none focus:border-sky focus:ring-2 focus:ring-sky/30"
          />
        </label>

        {error ? (
          <div className="mt-4 flex items-start gap-2 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
            <AlertIcon width={16} height={16} className="mt-0.5 shrink-0" />
            <span>{error}</span>
          </div>
        ) : null}

        <button
          type="submit"
          disabled={submitting}
          className="mt-5 w-full rounded-md bg-sky px-4 py-3 font-bold text-white transition hover:bg-sky-dark disabled:cursor-not-allowed disabled:bg-gray-300"
        >
          {submitting ? 'Entrando...' : 'Entrar'}
        </button>

        <p className="mt-4 text-center text-sm text-muted">
          ¿No tienes cuenta?{' '}
          <Link to="/registro" className="font-semibold text-sky hover:underline">
            Crear una cuenta
          </Link>
        </p>
      </form>

      <div className="mt-4 rounded-lg border border-dashed border-line bg-white/60 p-3 text-center text-xs text-muted">
        Cuenta de demostración: <span className="font-semibold text-ink">ana.garcia@ejemplo.com</span> ·{' '}
        <span className="font-semibold text-ink">demo1234</span>
      </div>
    </div>
  );
}
