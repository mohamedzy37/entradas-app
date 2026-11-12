import { Link } from 'react-router-dom';

export function NotFoundPage() {
  return (
    <div className="mx-auto max-w-lg px-4 py-20 text-center">
      <p className="text-6xl font-extrabold text-brand">404</p>
      <h1 className="mt-3 text-2xl font-extrabold text-ink">Página no encontrada</h1>
      <p className="mt-2 text-sm text-muted">
        La página que buscas no existe o ha cambiado de dirección.
      </p>
      <Link to="/" className="mt-6 inline-block rounded-md bg-sky px-5 py-3 font-bold text-white hover:bg-sky-dark">
        Volver al inicio
      </Link>
    </div>
  );
}
