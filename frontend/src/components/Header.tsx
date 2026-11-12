import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { EVENT_TYPES, eventTypeEmoji, eventTypeLabel } from '../lib/constants';
import { TicketIcon } from './Icons';

export function Header() {
  const [searchParams] = useSearchParams();
  const currentType = searchParams.get('type');
  const navigate = useNavigate();
  const { user, loading, logout } = useAuth();

  function handleLogout() {
    void logout().then(() => navigate('/'));
  }

  return (
    <header className="bg-brand text-white">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 pt-4">
        <Link to="/" className="flex items-center gap-2 rounded-md p-1 hover:bg-white/10">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-cta text-brand-dark">
            <TicketIcon width={20} height={20} />
          </span>
          <span className="text-xl font-extrabold tracking-tight">EntradasYa</span>
        </Link>

        <nav className="flex items-center gap-1 text-sm font-semibold">
          <Link to="/validar" className="hidden rounded-md px-3 py-2 hover:bg-white/10 sm:block">
            Validar entrada
          </Link>

          {loading ? null : user ? (
            <>
              {user.role !== 'CLIENT' ? (
                <Link to="/gestion" className="rounded-md px-3 py-2 hover:bg-white/10">
                  <span className="hidden md:inline">Gesti&oacute;n</span>
                  <span className="md:hidden">Panel</span>
                </Link>
              ) : null}
              <Link
                to="/cuenta"
                className="rounded-md px-3 py-2 hover:bg-white/10"
                title={user.email}
              >
                <span className="hidden md:inline">{user.name.split(' ')[0]} · </span>Mis entradas
              </Link>
              {user.role !== 'CLIENT' ? (
                <span
                  className="hidden rounded-full bg-cta px-2 py-0.5 text-xs font-bold text-brand-dark sm:inline"
                  title={`Rol: ${user.role}`}
                >
                  {user.role}
                </span>
              ) : null}
              <button
                type="button"
                onClick={handleLogout}
                className="rounded-md border border-white/40 px-3 py-2 hover:bg-white/10"
              >
                Salir
              </button>
            </>
          ) : (
            <>
              <Link to="/acceder" className="rounded-md px-3 py-2 hover:bg-white/10">
                Acceder
              </Link>
              <Link
                to="/registro"
                className="rounded-md bg-white px-3 py-2 text-brand hover:bg-white/90"
              >
                Crear cuenta
              </Link>
            </>
          )}
        </nav>
      </div>

      <div className="mx-auto max-w-6xl px-4">
        <div className="mt-3 flex items-center gap-1 overflow-x-auto pb-2 text-sm">
          <Link
            to="/eventos"
            className={`whitespace-nowrap rounded-full border px-3 py-1.5 font-semibold transition ${
              !currentType
                ? 'border-white bg-white/15'
                : 'border-transparent hover:border-white/40 hover:bg-white/10'
            }`}
          >
            Todos
          </Link>
          {EVENT_TYPES.map((type) => (
            <Link
              key={type}
              to={`/eventos?type=${type}`}
              className={`whitespace-nowrap rounded-full border px-3 py-1.5 font-semibold transition ${
                currentType === type
                  ? 'border-white bg-white/15'
                  : 'border-transparent hover:border-white/40 hover:bg-white/10'
              }`}
            >
              <span className="mr-1">{eventTypeEmoji(type)}</span>
              {eventTypeLabel(type)}
            </Link>
          ))}
        </div>
      </div>
    </header>
  );
}
