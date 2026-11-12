import { useState, type FormEvent } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { ApiError } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { AlertIcon, UserIcon } from '../components/Icons';

interface LocationState {
  from?: { pathname: string; search?: string };
}

export function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const from = (location.state as LocationState | null)?.from;
  const redirectTo = from ? `${from.pathname}${from.search ?? ''}` : '/';

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);

    if (name.trim().length < 2) {
      setError('Introduce tu nombre.');
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      setError('Introduce un correo electrónico válido.');
      return;
    }
    if (password.length < 8) {
      setError('La contraseña debe tener al menos 8 caracteres.');
      return;
    }
    if (!/[A-Za-z]/.test(password) || !/\d/.test(password)) {
      setError('La contraseña debe incluir letras y números.');
      return;
    }
    if (password !== confirm) {
      setError('Las contraseñas no coinciden.');
      return;
    }

    setSubmitting(true);
    try {
      await register({
        name: name.trim(),
        email: email.trim(),
        password,
        phone: phone.trim() || undefined,
      });
      navigate(redirectTo, { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'No se pudo crear la cuenta.');
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
        <h1 className="mt-3 text-2xl font-extrabold text-ink">Crea tu cuenta</h1>
        <p className="mt-1 text-sm text-muted">
          Regístrate para comprar entradas y consultarlas cuando quieras.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="mt-6 rounded-xl border border-line bg-white p-5">
        <label className="block">
          <span className="mb-1 block text-sm font-semibold text-ink">Nombre completo</span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Ana García"
            className="w-full rounded-md border border-line px-3 py-3 text-sm outline-none focus:border-sky focus:ring-2 focus:ring-sky/30"
          />
        </label>

        <label className="mt-4 block">
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
          <span className="mb-1 block text-sm font-semibold text-ink">Teléfono (opcional)</span>
          <input
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="+34 600 000 000"
            className="w-full rounded-md border border-line px-3 py-3 text-sm outline-none focus:border-sky focus:ring-2 focus:ring-sky/30"
          />
        </label>

        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="mb-1 block text-sm font-semibold text-ink">Contraseña</span>
            <input
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Mínimo 8 caracteres"
              className="w-full rounded-md border border-line px-3 py-3 text-sm outline-none focus:border-sky focus:ring-2 focus:ring-sky/30"
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-sm font-semibold text-ink">Repite la contraseña</span>
            <input
              type="password"
              autoComplete="new-password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              placeholder="••••••••"
              className="w-full rounded-md border border-line px-3 py-3 text-sm outline-none focus:border-sky focus:ring-2 focus:ring-sky/30"
            />
          </label>
        </div>

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
          {submitting ? 'Creando cuenta...' : 'Crear cuenta'}
        </button>

        <p className="mt-4 text-center text-sm text-muted">
          ¿Ya tienes cuenta?{' '}
          <Link to="/acceder" className="font-semibold text-sky hover:underline">
            Inicia sesión
          </Link>
        </p>
      </form>
    </div>
  );
}
