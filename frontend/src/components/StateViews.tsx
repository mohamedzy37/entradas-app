import { AlertIcon, Spinner } from './Icons';

export function Loading({ label = 'Cargando...' }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-muted">
      <Spinner className="text-sky" />
      <p className="text-sm">{label}</p>
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: Error; onRetry?: () => void }) {
  return (
    <div className="mx-auto max-w-lg rounded-lg border border-red-200 bg-red-50 p-6 text-center">
      <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-red-100 text-red-600">
        <AlertIcon />
      </div>
      <h3 className="font-bold text-red-800">Algo ha ido mal</h3>
      <p className="mt-1 text-sm text-red-700">{error.message}</p>
      {onRetry ? (
        <button
          onClick={onRetry}
          className="mt-4 rounded-md bg-red-600 px-4 py-2 text-sm font-bold text-white hover:bg-red-700"
        >
          Reintentar
        </button>
      ) : null}
    </div>
  );
}

export function EmptyState({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="rounded-lg border border-line bg-white p-10 text-center">
      <p className="text-4xl">🔍</p>
      <h3 className="mt-2 font-bold text-ink">{title}</h3>
      {subtitle ? <p className="mt-1 text-sm text-muted">{subtitle}</p> : null}
    </div>
  );
}
