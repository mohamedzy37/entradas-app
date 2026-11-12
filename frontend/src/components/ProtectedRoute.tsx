import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import type { Role } from '../api/types';
import { useAuth } from '../auth/AuthContext';
import { Loading } from './StateViews';

interface ProtectedRouteProps {
  children: ReactNode;
  /** Si se indica, el usuario debe tener uno de estos roles. */
  roles?: Role[];
}

/**
 * Envuelve rutas que requieren sesion. Si el usuario no esta autenticado,
 * redirige a /acceder guardando el destino para volver tras iniciar sesion.
 * Si se exige un rol y no lo tiene, muestra un aviso de acceso denegado.
 */
export function ProtectedRoute({ children, roles }: ProtectedRouteProps) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return <Loading label="Comprobando tu sesi\u00f3n..." />;
  }

  if (!user) {
    return <Navigate to="/acceder" state={{ from: location }} replace />;
  }

  if (roles && roles.length > 0 && !roles.includes(user.role)) {
    return <Forbidden roles={roles} />;
  }

  return <>{children}</>;
}

function Forbidden({ roles }: { roles: Role[] }) {
  return (
    <div className="mx-auto max-w-lg px-4 py-16 text-center">
      <div className="rounded-xl border border-line bg-white p-8">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-red-100 text-red-600">
          <span className="text-2xl">&#128274;</span>
        </div>
        <h1 className="mt-4 text-xl font-extrabold text-ink">Acceso restringido</h1>
        <p className="mt-2 text-sm text-muted">
          Esta secci&oacute;n solo est&aacute; disponible para los roles{' '}
          <span className="font-semibold text-ink">{roles.join(', ')}</span>. Has iniciado sesi&oacute;n
          con otra cuenta.
        </p>
      </div>
    </div>
  );
}
