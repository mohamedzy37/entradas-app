import { useEffect, useState } from 'react';
import { api } from '../api/client';

/**
 * Boton "Continuar con Google". Solo se muestra si el backend tiene el login
 * con Google configurado (GET /api/auth/providers).
 *
 * Es un enlace normal, no un fetch: el navegador va a la API, que redirige a
 * Google (OpenID Connect con PKCE) y despues vuelve a /acceder/google.
 * No se carga ningun script de Google en la pagina.
 */
export function GoogleButton({ next, label = 'Continuar con Google' }: { next: string; label?: string }) {
  const [enabled, setEnabled] = useState(false);

  useEffect(() => {
    let active = true;
    api
      .authProviders()
      .then((response) => {
        if (active) setEnabled(response.data.google);
      })
      .catch(() => {
        /* sin proveedores externos */
      });
    return () => {
      active = false;
    };
  }, []);

  if (!enabled) return null;

  return (
    <>
      <div className="my-4 flex items-center gap-3 text-xs text-muted">
        <span className="h-px flex-1 bg-line" />o<span className="h-px flex-1 bg-line" />
      </div>
      <a
        href={api.googleLoginUrl(next)}
        className="flex w-full items-center justify-center gap-2 rounded-md border border-line bg-white px-4 py-3 font-semibold text-ink transition hover:bg-gray-50"
      >
        <span
          aria-hidden="true"
          className="flex h-6 w-6 items-center justify-center rounded-full border border-line text-sm font-extrabold text-sky"
        >
          G
        </span>
        {label}
      </a>
    </>
  );
}
